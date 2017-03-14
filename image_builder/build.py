import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from keystoneauth1.identity import v3
from keystoneauth1 import session
from novaclient import client as novaclient
from novaclient import exceptions

class BuildFunctions:
  def __init__(self,
               session,
               region,
               image_name,
               az,
               source_image,
               ssh_user,
               provision_script,
               template_dir,
               download_dir):
      self.session = session
      self.image_name = image_name
      self.az = az
      self.source_image = source_image
      self.ssh_user = ssh_user
      self.provision_script = provision_script
      self.template_dir = template_dir
      self.download_dir = download_dir
      self.tmp_dir = self.__make_tmp_dir()
      self.nova = novaclient.Client("2", session=session, region_name=region)

  def cleanup(self, secgroup_id, keypair_id):
      logging.info('Removing temporary security group...')
      self.nova.security_groups.delete(group=secgroup_id)
      logging.info('Removing temporary keypair...')
      self.nova.keypairs.delete(key=keypair_id)
      logging.info('Removing temporary directory with content...')
      shutil.rmtree(self.tmp_dir)

  def create_keypairs(self):
      keyname = "imagebuilder-" + str(uuid.uuid4().hex)
      keypair = self.nova.keypairs.create(name=keyname)
      private_key = keypair.private_key
      '''We need to convert the generated RSA-key from BER to DER because of
      https://github.com/mitchellh/packer/issues/2526'''
      with tempfile.NamedTemporaryFile(delete=True) as temp:
          temp.write(bytes(private_key, 'ascii'))
          temp.flush()
          keypath=os.path.join(self.tmp_dir,'packerKey')
          openssl_cmd = ['openssl', 'rsa', '-in', temp.name, '-out', keypath]
          p = subprocess.Popen(openssl_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
          p.wait()
          os.chmod(keypath, 0o600)
      logging.info("Saved private key in %s" % keypath)
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
      cmd = ['glance', 'image-download', '--file', os.path.join(self.download_dir,filename), artifact_id]
      p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
      with p.stdout:
        self.__log_subprocess_output(p.stdout)
      exitcode = p.wait()
      return exitcode

  def parse_manifest(self):
      with open(os.path.join(self.tmp_dir,'packer-manifest.json')) as data_file:
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
      manifest_path_var = 'manifest_path=' + self.tmp_dir + 'packer-manifest.json'
      cmd = ['packer','build',
             '-color=false',
             '--var', image_name_var,
             '--var', sshuser_var,
             '--var', secgroup_var,
             '--var', source_image_var,
             '--var', keyname_var,
             '--var', az_var,
             '--var', provision_script_var,
             '--var', manifest_path_var,
             os.path.join(self.template_dir,'template')]
      p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
      with p.stdout:
        self.__log_subprocess_output(p.stdout)
      exitcode = p.wait()
      return exitcode

  def __make_tmp_dir(self):
      logging.info('Creating a directory for temporary files...')
      tmp_dir = tempfile.mkdtemp(prefix='imagebuilder-')
      return tmp_dir

  def __log_subprocess_output(self, pipe):
      for line in iter(pipe.readline, b''):
          logging.info('%r', line)
