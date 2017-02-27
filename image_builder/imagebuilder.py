#!/usr/bin/python3

import json
import logging
import os
import subprocess
import sys
import tempfile
import uuid
import argparse
from .parsecommands import Commands
from .build import BuildFunctions
from keystoneauth1.identity import v3
from keystoneauth1 import session
from novaclient import client as novaclient

class ImageBuilder:
    def auth(self, rc):
        auth = v3.Password(auth_url=rc['auth_url'],
                           username=rc['username'],
                           password=rc['password'],
                           user_domain_name=rc['user_domain_name'],
                           project_domain_name=rc['project_domain_name'])
        sess = session.Session(auth)
        return sess

    def get_os_env(self):
        c = {}
        c['username'] = os.environ['OS_USERNAME']
        c['tenant_name'] = os.environ['OS_TENANT_NAME']
        c['password'] = os.environ['OS_PASSWORD']
        c['auth_url'] = os.environ['OS_AUTH_URL']
        c['api_version'] = os.environ['OS_IDENTITY_API_VERSION']
        c['domain_name'] = os.environ['OS_DOMAIN_NAME']
        c['user_domain_name'] = os.environ['OS_USER_DOMAIN_NAME']
        c['project_domain_name'] = os.environ['OS_PROJECT_DOMAIN_NAME']
        c['region_name'] = os.environ['OS_REGION_NAME']
        c['no_cache'] = os.environ['OS_NO_CACHE']
        return c

def main():
    commands = Commands()
    ib = ImageBuilder()

    try:
        rc = ib.get_os_env()
    except:
        print("Failed to read environment variables.\nPlease run:\n  source <my_openrc>\nand try again.")
        sys.exit(1)

    session = ib.auth(rc)
    region = rc['region_name']

    if commands.build_args:
        image_name = commands.build_args.name
        az = commands.build_args.availability_zone
        source_image = commands.build_args.source_image
        sshuser = commands.build_args.ssh_username
        provision_script = commands.build_args.provision_script

        if commands.build_args.verbose:
            logging.basicConfig(format="%(message)s", level=logging.INFO)
        elif commands.build_args.debug:
            logging.basicConfig(level=logging.DEBUG)

        build = BuildFunctions(session,
                               region,
                               image_name,
                               az,
                               source_image,
                               sshuser,
                               provision_script)

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

        sys.exit(exitcode)
