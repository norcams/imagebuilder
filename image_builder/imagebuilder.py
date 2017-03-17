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
    #pylint: disable=invalid-name
    def auth(rc):
        auth = v3.Password(auth_url=rc['auth_url'],
                           username=rc['username'],
                           password=rc['password'],
                           user_domain_name=rc['user_domain_name'],
                           project_domain_name=rc['project_domain_name'])
        sess = session.Session(auth)
        return sess

    @staticmethod
    def get_os_env():
        config = {}
        config['username'] = os.environ['OS_USERNAME']
        config['tenant_name'] = os.environ['OS_TENANT_NAME']
        config['password'] = os.environ['OS_PASSWORD']
        config['auth_url'] = os.environ['OS_AUTH_URL']
        config['api_version'] = os.environ['OS_IDENTITY_API_VERSION']
        config['domain_name'] = os.environ['OS_DOMAIN_NAME']
        config['user_domain_name'] = os.environ['OS_USER_DOMAIN_NAME']
        config['project_domain_name'] = os.environ['OS_PROJECT_DOMAIN_NAME']
        config['region_name'] = os.environ['OS_REGION_NAME']
        config['no_cache'] = os.environ['OS_NO_CACHE']
        config['template_dir'] = os.environ['IB_TEMPLATE_DIR'] if "IB_TEMPLATE_DIR" in os.environ else None
        config['download_dir'] = os.environ['IB_DOWNLOAD_DIR'] if "IB_DOWNLOAD_DIR" in os.environ else None
        return config

def main():
    commands = Commands()
    imagebuilder = ImageBuilder()

    try:
        # pylint: disable=invalid-name
        rc = imagebuilder.get_os_env()
    except KeyError:
        print("Failed to read environment variables.\nPlease run:\n  source <my_openrc>\nand try again.")
        sys.exit(1)

    ib_session = imagebuilder.auth(rc)
    region = rc['region_name']

    config = Config().config

    template_dir = rc['template_dir'] or config.get('main', 'template_dir')
    download_dir = rc['download_dir'] or config.get('main', 'download_dir')

    if commands.build_args:
        image_name = commands.build_args.name
        avail_zone = commands.build_args.availability_zone
        source_image = commands.build_args.source_image
        sshuser = commands.build_args.ssh_username
        provision_script = commands.build_args.provision_script

        if commands.build_args.verbose:
            logging.basicConfig(format="%(message)s", level=logging.INFO)
        elif commands.build_args.debug:
            logging.basicConfig(level=logging.DEBUG)

        build = BuildFunctions(ib_session,
                               region,
                               image_name,
                               avail_zone,
                               source_image,
                               sshuser,
                               provision_script,
                               template_dir,
                               download_dir)

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
        helpers.clean_tmp_files(build.tmp_dir)

        sys.exit(exitcode)

    if commands.bootstrap_args:
        image_name = commands.bootstrap_args.name
        avail_zone = commands.bootstrap_args.availability_zone
        url = commands.bootstrap_args.url
        checksum_url = commands.bootstrap_args.checksum_url
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
        image_file = bootstrap.download_and_check(url, checksum_url)

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
