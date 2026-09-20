import json
import logging
import os
import subprocess
import time
import uuid

from openstack.connection import Connection

from . import helpers

log = logging.getLogger(__name__)

class BuildFunctions:
    def __init__(self,
                 session,
                 region,
                 *,
                 image_name,
                 avail_zone,
                 flavor,
                 source_image,
                 ssh_user,
                 provision_script,
                 template_dir,
                 download_dir):
        self.session = session
        self.image_name = image_name
        self.avail_zone = avail_zone
        self.flavor = flavor
        self.source_image = source_image
        self.ssh_user = ssh_user
        self.provision_script = provision_script
        self.template_dir = template_dir
        self.download_dir = download_dir
        self.tmp_dir = helpers.make_tmp_dir()
        # Only the connection is built here. Reaching for a proxy such as
        # conn.network authenticates and discovers endpoints, so that is left
        # to the call sites to keep this constructor free of network traffic
        self.conn = Connection(session=session, region_name=region)

    def cleanup(self, secgroup_id, keypair_id):
        """Cleans up the mess we've made

        Runs from a finally block, so it has to cope with a build that only got
        half way and must not raise on its way out: an exception here would
        mask whatever actually went wrong.
        """
        if secgroup_id:
            log.info('Removing temporary security group...')
            try:
                self.conn.network.delete_security_group(secgroup_id)
            except Exception as error:
                log.warning("Failed to remove security group %s: %s", secgroup_id, error)
        if keypair_id:
            log.info('Removing temporary keypair...')
            try:
                self.conn.compute.delete_keypair(keypair_id)
            except Exception as error:
                log.warning("Failed to remove keypair %s: %s", keypair_id, error)

    def create_keypairs(self):
        """Creates a temporary keypair"""

        keyname = f"imagebuilder-{uuid.uuid4().hex}"
        keypath = os.path.join(self.tmp_dir, keyname)
        # No shell: there is nothing here a shell is needed for, and letting
        # PATH find ssh-keygen beats hardcoding where it lives
        cmd = ['ssh-keygen', '-b', '521', '-t', 'ecdsa', '-N', '', '-f', keypath]
        log.debug(cmd)
        out = subprocess.run(cmd, check=False).returncode   # generate temporary ssh key
        if out:                                        # something went wrong with the key generation
            log.error("Failed to generate SSH key, ssh-keygen exited %s", out)
            return None, None
        # read public key string and store into Openstack
        with open(keypath + ".pub", encoding="utf-8") as pubfile:
            pubkeystring = pubfile.read().replace('\n', '')
        keypair = self.conn.compute.create_keypair(name=keyname,
                                                   public_key=pubkeystring)
        return keyname, keypair.id

    def create_security_group(self):
        """Creates a temporary security group"""
        secgroup_name = f"imagebuilder-{uuid.uuid4().hex}"
        secgroup = self.conn.network.create_security_group(
            name=secgroup_name,
            description='Temporary security group for image building')
        log.info('Creating rule allowing SSH traffic...')
        for ethertype in ('IPv4', 'IPv6'):
            self.conn.network.create_security_group_rule(
                security_group_id=secgroup.id,
                direction='ingress',
                protocol='tcp',
                port_range_min=22,
                port_range_max=22,
                ethertype=ethertype)
        return secgroup_name, secgroup.id

    def delete_image(self, image_id):
        if image_id is None:
            log.warning('No image to remove')
            return False
        log.info("Removing image %s", image_id)
        try:
            self.conn.image.delete_image(image_id)
        except Exception as error:
            log.error("Removing image %s failed: %s", image_id, error)
            return False
        return True

    def download_image(self, artifact_id):
        """Downloads image from Glance

        Straight through the API on the session we already hold. Shelling out
        to the glance CLI meant a second, independent authentication from the
        OS_* environment, and that CLI is deprecated upstream.

        stream=True is load bearing. Without it openstacksdk asks requests for
        the whole response body up front, so the entire image is held in
        memory before a byte of it is written, and a large image takes the
        process out via the OOM killer.
        """
        timestr = time.strftime("%Y%m%d")
        filename = f'{self.image_name}-{timestr}.qcow2'
        target = os.path.join(self.download_dir, filename)
        log.info("Downloading image to %s...", target)
        try:
            with open(target, 'wb') as image_file:
                self.conn.image.download_image(artifact_id,
                                               output=image_file,
                                               stream=True)
        except Exception as error:
            log.error("Failed to download image %s: %s", artifact_id, error)
            if os.path.exists(target):
                os.remove(target)          # don't leave a half-written image behind
            return 1
        log.info('Download successful, deleting from Glance...')
        self.delete_image(artifact_id)
        return 0

    def find_network_id(self, name):
        # networks() rather than find_network(), which raises on a duplicate
        # name where this has always just taken the first match
        network = next(self.conn.network.networks(name=name), None)
        if network:
            network_id = network.id
            log.info("Found network %s with id %s", name, network_id)
        else:
            network_id = False
            log.error("Cannot find network %s", name)
        return network_id

    def find_template(self):
        """Finds the Packer template in template_dir

        The HCL2 template is preferred. A legacy JSON template (a file simply
        named 'template') is still accepted so existing template_dir setups
        keep working, but it cannot declare required_plugins.
        """
        for name in ('template.pkr.hcl', 'template'):
            template_path = os.path.join(self.template_dir, name)
            if os.path.isfile(template_path):
                if name == 'template':
                    log.warning("Using legacy JSON template %s", template_path)
                    log.warning("Packer no longer bundles the openstack builder. "
                                "Install it manually with 'packer plugins install "
                                "github.com/hashicorp/openstack', or migrate to "
                                "template.pkr.hcl")
                return template_path
        log.error("No Packer template found in %s", self.template_dir)
        return None

    def parse_manifest(self):
        """Parses the manifest file generated by packer

        Packer exiting successfully does not guarantee the manifest
        post-processor left a usable file behind, so report that rather than
        raising and taking the build down with a traceback.
        """
        manifest_path = os.path.join(self.tmp_dir, 'packer-manifest.json')
        try:
            with open(manifest_path, encoding="utf-8") as data_file:
                manifest = json.load(data_file)
            return manifest['builds'][0]['artifact_id']
        except (OSError, ValueError, KeyError, IndexError) as error:
            log.error("Failed to read the image id from %s: %s", manifest_path, error)
            return None

    def run_packer(self, template_path, secgroup_name, key_name, network_id):
        """Executes Packer command"""
        image_name_var = f'image_name={self.image_name}'
        avail_zone_var = f'availability_zone={self.avail_zone}'
        secgroup_var = f'security_group={secgroup_name}'
        sshuser_var = f'ssh_username={self.ssh_user}'
        keyname_var = f'ssh_keypair_name={key_name}'                           # key as it is named in Openstack
        keypath_var = f'ssh_key_path={os.path.join(self.tmp_dir, key_name)}'   # the "real" private key
        flavor_var = f'flavor={self.flavor}'
        network_var = f'network={network_id}'
        source_image_var = f'source_image={self.source_image}'
        provision_script_var = f'provision_script={self.provision_script}'
        manifest_path_var = f"manifest_path={os.path.join(self.tmp_dir, 'packer-manifest.json')}"
        cmd = ['packer', 'build',
               '-color=false',
               '-var', image_name_var,
               '-var', sshuser_var,
               '-var', secgroup_var,
               '-var', flavor_var,
               '-var', network_var,
               '-var', source_image_var,
               '-var', keyname_var,
               '-var', keypath_var,
               '-var', avail_zone_var,
               '-var', provision_script_var,
               '-var', manifest_path_var,
               template_path]
        log.debug(cmd)
        with subprocess.Popen(cmd, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT) as process:
            helpers.log_subprocess_output(process.stdout)
            return process.wait()

    def openstack_plugin_installed(self):
        """Whether Packer can already see the openstack builder

        'packer plugins installed' exits 0 whether or not anything is there, so
        the answer is in the output rather than the status.
        """
        try:
            installed = subprocess.run(['packer', 'plugins', 'installed'],
                                       capture_output=True, text=True,
                                       check=False)
        except OSError as error:
            log.error("Could not run packer: %s", error)
            return False
        log.debug(installed.stdout)
        return 'openstack' in installed.stdout

    def run_packer_init(self, template_path):
        """Installs the Packer plugins required by the template

        Packer does not bundle builder plugins anymore, so the openstack
        builder has to be installed before the build. Only HCL2 templates can
        declare required_plugins, so for a legacy JSON template there is
        nothing to install from: all this can do is check that someone already
        installed it by hand, and say so now rather than let packer fail with
        'the builder openstack is unknown' once the temporary security group
        and keypair already exist.
        """
        if not template_path.endswith('.pkr.hcl'):
            if self.openstack_plugin_installed():
                return 0
            log.error("The openstack builder is not installed, and %s is a "
                      "legacy JSON template so it cannot declare it. Either "
                      "run 'packer plugins install "
                      "github.com/hashicorp/openstack', or migrate to "
                      "template.pkr.hcl", template_path)
            return 1
        cmd = ['packer', 'init', template_path]
        log.debug(cmd)
        with subprocess.Popen(cmd, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT) as process:
            helpers.log_subprocess_output(process.stdout)
            return process.wait()
