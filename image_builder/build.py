import json
import logging
import os
import subprocess
import sys
import tempfile
import time
import uuid
from novaclient import client as novaclient
from neutronclient.v2_0 import client as neutronclient
from .helpers import Helpers as helpers

class BuildFunctions(object):
    def __init__(self,
                 session,
                 region,
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
        self.nova = novaclient.Client("2", session=session, region_name=region)
        self.neutron = neutronclient.Client(session=session, region_name=region)

    def cleanup(self, secgroup_id, keypair_id):
        """Cleans up the mess we've made"""
        logging.info('Removing temporary security group...')
        self.neutron.delete_security_group(secgroup_id)
        logging.info('Removing temporary keypair...')
        self.nova.keypairs.delete(key=keypair_id)

    def create_keypairs(self):
        """Creates a temporary keypair"""
        keyname = "imagebuilder-" + str(uuid.uuid4().hex)
        keypair = self.nova.keypairs.create(name=keyname)
        private_key = keypair.private_key
        '''We need to convert the generated RSA-key from BER to DER because of
        https://github.com/mitchellh/packer/issues/2526'''
        with tempfile.NamedTemporaryFile(delete=True) as temp:
            temp.write(bytes(private_key, 'ascii'))
            temp.flush()
            keypath = os.path.join(self.tmp_dir, 'packerKey')
            openssl_cmd = ['openssl', 'rsa', '-in', temp.name, '-out', keypath]
            process = subprocess.Popen(openssl_cmd,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT)
            process.wait()
            os.chmod(keypath, 0o600)
            #pylint: disable=logging-not-lazy
            logging.info("Saved private key in %s" % keypath)
        return keyname, keypair.id

    def create_security_group(self):
        """Creates a temporary security group"""
        secgroup_name = "imagebuilder-" + str(uuid.uuid4().hex)
        # pylint: disable=line-too-long
        secgroup = self.neutron.create_security_group(body={
            'security_group':
            {
                'name': secgroup_name,
                'description': 'Temporary security group for image building'
            }
        })
        secgroup_id = secgroup['security_group']['id']
        logging.info('Creating rule allowing SSH traffic...')
        self.neutron.create_security_group_rule(body={
            'security_group_rule':
            {
                'security_group_id': secgroup_id,
                'direction': 'ingress',
                'protocol': 'tcp',
                'port_range_min': 22,
                'port_range_max': 22,
                'ethertype': 'IPv4'
            }
        })
        self.neutron.create_security_group_rule(body={
            'security_group_rule':
            {
                'security_group_id': secgroup_id,
                'direction': 'ingress',
                'protocol': 'tcp',
                'port_range_min': 22,
                'port_range_max': 22,
                'ethertype': 'IPv6'
            }
        })
        return secgroup_name, secgroup_id

    def delete_image(self, image_id):
        logging.info('Removing image %s' % image_id)
        #self.nova.images.delete(image_id)
        if(image_id is not None):
            try:
                logging.info('Removing image %s' % image_id)
                self.nova.images.delete(image_id)
                return True
        except:
                logging.info('Removing image failed.')
                return False

    def download_image(self, artifact_id):
        """Downloads image from Glance"""
        logging.info('Downloading image...')
        timestr = time.strftime("%Y%m%d")
        filename = self.image_name + '-' + timestr + '.qcow2'
        cmd = ['glance',
               'image-download',
               '--file', os.path.join(self.download_dir, filename),
               artifact_id]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        with process.stdout:
            helpers.log_subprocess_output(process.stdout)
        exitcode = process.wait()
        # Not so pretty but will do for now
        if exitcode == 0:
            logging.info('Download successful, deleting from Glance...')
            self.delete_image(artifact_id)
        return exitcode

    def find_network_id(self, name):
        networks = self.neutron.list_networks(name=name)
        if networks['networks']:
            network_id = networks['networks'][0]['id']
            logging.info("Found network %s with id %s" % (name, network_id))
        else:
            network_id = False
            logging.info("Cannot find network %s" % name)
        return network_id

    def parse_manifest(self):
        """Parses the manifest file generated by packer"""
        with open(os.path.join(self.tmp_dir, 'packer-manifest.json')) as data_file:
            manifest = json.load(data_file)
        artifact_id = manifest['builds'][0]['artifact_id']
        return artifact_id

    def run_packer(self, secgroup_name, key_name, network_id):
        """Executes Packer command"""
        image_name_var = 'image_name=' + self.image_name
        avail_zone_var = 'availability_zone=' + self.avail_zone
        secgroup_var = 'security_group=' + secgroup_name
        sshuser_var = 'ssh_username=' + self.ssh_user
        keyname_var = 'ssh_keypair_name=' + key_name
        keypath_var = 'ssh_key_path=' + os.path.join(self.tmp_dir, 'packerKey')
        flavor_var = 'flavor=' + self.flavor
        network_var = 'network=' + network_id
        source_image_var = 'source_image=' + self.source_image
        provision_script_var = 'provision_script=' + self.provision_script
        manifest_path_var = 'manifest_path=' + os.path.join(self.tmp_dir, 'packer-manifest.json')
        cmd = ['packer', 'build',
               '-color=false',
               '--var', image_name_var,
               '--var', sshuser_var,
               '--var', secgroup_var,
               '--var', flavor_var,
               '--var', network_var,
               '--var', source_image_var,
               '--var', keyname_var,
               '--var', keypath_var,
               '--var', avail_zone_var,
               '--var', provision_script_var,
               '--var', manifest_path_var,
               os.path.join(self.template_dir, 'template')]
        logging.debug(cmd)
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        with process.stdout:
            helpers.log_subprocess_output(process.stdout)
        exitcode = process.wait()
        return exitcode
