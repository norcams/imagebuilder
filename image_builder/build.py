import json
import logging
import os
import subprocess
import sys
import tempfile
import uuid
from keystoneauth1.identity import v3
from keystoneauth1 import session
from novaclient import client as novaclient
from novaclient import exceptions

class BuildFunctions:
  def __init__(self, session, region, image_name, az, source_image, ssh_user, provision_script):
      self.session = session
      self.image_name = image_name
      self.az = az
      self.source_image = source_image
      self.ssh_user = ssh_user
      self.provision_script = provision_script
      self.nova = novaclient.Client("2", session=session, region_name=region)

  def cleanup(self, secgroup_id, keypair_id):
      logging.info('Removing temporary security group...')
      self.nova.security_groups.delete(group=secgroup_id)
      logging.info('Removing temporary keypair...')
      self.nova.keypairs.delete(key=keypair_id)
      logging.info('Removing local private key...')
      os.remove('packerKey')
      logging.info('Removing Packer manifest file...')
      if os.path.exists('packer-manifest.json'):
          os.remove('packer-manifest.json')

  def create_keypairs(self):
      keyname = "imagebuilder-" + str(uuid.uuid4().hex)
      keypair = self.nova.keypairs.create(name=keyname)
      private_key = keypair.private_key
      '''We need to convert the generated RSA-key from BER to DER because of
      https://github.com/mitchellh/packer/issues/2526'''
      with tempfile.NamedTemporaryFile(delete=True) as temp:
          temp.write(bytes(private_key, 'ascii'))
          temp.flush()
          openssl_cmd = ['openssl', 'rsa', '-in', temp.name, '-out', 'packerKey']
          p = subprocess.Popen(openssl_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
          p.wait()
          os.chmod("packerKey", 0o600)
      logging.info("Saved private key in %s" % keyname)
      return keyname, keypair.id

  def create_security_group(self):
      secgroup_name = "imagebuilder-" + str(uuid.uuid4().hex)
      secgroup = self.nova.security_groups.create(name=secgroup_name,
                                             description='Temporary security group for image building')
      logging.info('Creating rule allowing SSH traffic...')
      self.nova.security_group_rules.create(secgroup.id,
                                       ip_protocol="tcp",
                                       from_port=22,
                                       to_port=22)
      return secgroup_name, secgroup.id

  def download_image(self, artifact_id):
      logging.info('Downloading image...')
      filename = self.image_name + '.raw'
      cmd = ['glance', 'image-download', '--file', filename, artifact_id]
      p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
      with p.stdout:
        self.__log_subprocess_output(p.stdout)
      exitcode = p.wait()
      return exitcode

  def parse_manifest(self):
      with open('packer-manifest.json') as data_file:
          manifest = json.load(data_file)
      artifact_id = manifest['builds'][0]['artifact_id']
      return artifact_id

  def run_packer(self, secgroup_name, key_name):
      image_name_var = 'image_name=' + self.image_name
      az_var = 'availability_zone=' + self.az
      secgroup_var = 'security_group=' + secgroup_name
      sshuser_var = 'ssh_username=' + self.ssh_user
      keyname_var = 'ssh_keypair_name=' + key_name
      source_image_var = 'source_image=' + self.source_image
      provision_script_var = 'provision_script=' + self.provision_script
      cmd = ['packer','build',
             '-color=false',
             '--var', image_name_var,
             '--var', sshuser_var,
             '--var', secgroup_var,
             '--var', source_image_var,
             '--var', keyname_var,
             '--var', az_var,
             '--var', provision_script_var,
             'template']
      p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
      with p.stdout:
        self.__log_subprocess_output(p.stdout)
      exitcode = p.wait()
      return exitcode

  def __log_subprocess_output(self, pipe):
      for line in iter(pipe.readline, b''):
          logging.info('%r', line)
