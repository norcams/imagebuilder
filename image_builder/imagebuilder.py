#!/usr/bin/python3

import logging
import os
import sys
from keystoneauth1.identity import v3
from keystoneauth1 import session
from .parsecommands import Commands
from .build import BuildFunctions
from .bootstrap import BootstrapFunctions
from .config import Config
from .helpers import Helpers as helpers

class ImageBuilder(object):
    @staticmethod
    def auth(rc):
        auth = v3.Password(auth_url=rc['auth_url'],
                           project_name=rc['project_name'],
                           username=rc['username'],
                           password=rc['password'],
                           user_domain_name=rc['user_domain_name'],
                           project_domain_name=rc['project_domain_name'])
        if rc['cacert'] is not None:
            sess = session.Session(auth,
                                   verify=rc['cacert'])
        else:
            sess = session.Session(auth)
        return sess

    @staticmethod
    def get_openstack_rc():
        env_var = {}
        env_var['username'] = os.environ['OS_USERNAME']
        env_var['project_name'] = os.environ['OS_PROJECT_NAME']
        env_var['cacert'] = os.environ['OS_CACERT'] if "OS_CACERT" in os.environ else None
        env_var['password'] = os.environ['OS_PASSWORD']
        env_var['auth_url'] = os.environ['OS_AUTH_URL']
        env_var['api_version'] = os.environ['OS_IDENTITY_API_VERSION']
        env_var['user_domain_name'] = os.environ['OS_USER_DOMAIN_NAME']
        env_var['project_domain_name'] = os.environ['OS_PROJECT_DOMAIN_NAME']
        env_var['region_name'] = os.environ['OS_REGION_NAME']
        env_var['no_cache'] = os.environ['OS_NO_CACHE']
        return env_var

def main():
    commands = Commands()
    imagebuilder = ImageBuilder()

    try:
        rc = imagebuilder.get_openstack_rc()
    except KeyError:
        print("""Failed to read environment variables.
Please run:
  source <my_openrc>
and try again.""")
        sys.exit(1)

    ib_session = imagebuilder.auth(rc)
    region = rc['region_name']

    config = Config().config

    if "IB_TEMPLATE_DIR" in os.environ:
        template_dir = os.environ['IB_TEMPLATE_DIR']
    else:
        try:
            template_dir = config.get('main', 'template_dir')
        except:
            print("Failed to read template_dir from config")
            sys.exit(1)

    if "IB_DOWNLOAD_DIR" in os.environ:
        download_dir = os.environ['IB_DOWNLOAD_DIR']
    else:
        try:
            download_dir = config.get('main', 'download_dir')
        except:
            print("Failed to read download_dir from config")
            sys.exit(1)

    if commands.build_args:
        image_name = commands.build_args.name
        avail_zone = commands.build_args.availability_zone
        flavor = commands.build_args.flavor
        source_image = commands.build_args.source_image
        sshuser = commands.build_args.ssh_username
        provision_script = commands.build_args.provision_script
        network_name = commands.build_args.network_name

        if commands.build_args.verbose:
            logging.basicConfig(format="%(message)s", level=logging.INFO)
        elif commands.build_args.debug:
            logging.basicConfig(level=logging.DEBUG)

        build = BuildFunctions(ib_session,
                               region,
                               image_name,
                               avail_zone,
                               flavor,
                               source_image,
                               sshuser,
                               provision_script,
                               template_dir,
                               download_dir,
                               network_name)

        logging.info('Creating Packer security group...')
        secgroup_name, secgroup_id = build.create_security_group()

        logging.info('Creating Packer keypair...')
        key_name, keypair_id = build.create_keypairs()

        logging.info('Running Packer...')
        exitcode = build.run_packer(secgroup_name, key_name)
        if exitcode == 0:
            artifact_id = build.parse_manifest()
            logging.info("Successfully created image id %s" % artifact_id)
            if commands.build_args.download:
                exitcode = build.download_image(artifact_id)
            else:
                exitcode = 0
        else:
            logging.info('Build failed')
            exitcode = 1

        logging.info('Cleaning up...')
        build.cleanup(secgroup_id, keypair_id)
        if commands.build_args.purge_source:
            build.delete_image(source_image)
        helpers.clean_tmp_files(build.tmp_dir)

        sys.exit(exitcode)

    if commands.bootstrap_args:
        image_name = commands.bootstrap_args.name
        avail_zone = commands.bootstrap_args.availability_zone
        url = commands.bootstrap_args.url
        checksum_url = commands.bootstrap_args.checksum_url
        checksum_digest = commands.bootstrap_args.checksum_digest
        disk_format = commands.bootstrap_args.disk_format
        min_disk = int(commands.bootstrap_args.min_disk)
        min_ram = int(commands.bootstrap_args.min_ram)

        if commands.bootstrap_args.verbose:
            logging.basicConfig(format="%(message)s", level=logging.INFO)
        elif commands.bootstrap_args.debug:
            logging.basicConfig(level=logging.DEBUG)

        bootstrap = BootstrapFunctions(ib_session,
                                       region,
                                       avail_zone)
        logging.info('Downloading image...')
        image_file = bootstrap.download_and_check(url, checksum_url, checksum_digest)

        if image_file:
            logging.info('Uploading image to Glance...')
            image_id = bootstrap.create_glance_image(image_file,
                                                     image_name,
                                                     disk_format,
                                                     min_disk,
                                                     min_ram)
        else:
            logging.info('Downloading failed.')
            logging.info('Cleaning up...')
            helpers.clean_tmp_files(bootstrap.tmp_dir)
            sys.exit(1)

        if image_id:
            sys.stdout.write(image_id)
        else:
            logging.info('Uploading failed.')
            logging.info('Cleaning up...')
            helpers.clean_tmp_files(bootstrap.tmp_dir)
            sys.exit(1)

        logging.info('Cleaning up...')
        helpers.clean_tmp_files(bootstrap.tmp_dir)
        sys.exit(0)

# vim: set ft=python3
