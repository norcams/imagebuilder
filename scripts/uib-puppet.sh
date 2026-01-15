#!/bin/bash

# Source information about the operating system we are running on
. /etc/os-release

# Install different versions of puppet repo and agent based on Enterprise Linux version
if [[ `echo $VERSION_ID | /bin/cut -d '.' -f1` -eq 8 ]]; then
  sudo yum install -y redhat-lsb-core.x86_64
  sudo yum install -y https://yum.puppetlabs.com/puppet7-release-el-"$(lsb_release -sr|cut -d'.' -f1)".noarch.rpm
  sudo yum install -y puppet-agent
elif [[ `echo $VERSION_ID | /bin/cut -d '.' -f1` -eq 10 ]]; then
  sudo dnf install -y https://yum.voxpupuli.org/openvox7-release-el-"$(echo $VERSION_ID | cut -d'.' -f1)".noarch.rpm
  sudo dnf install -y openvox-agent
fi

# Install theforman module
sudo /opt/puppetlabs/bin/puppet module install theforeman/puppet

# Create dir for UiB spesifics
sudo mkdir /opt/uib

# Create file to indicate first boot
sudo touch /opt/uib/uib-firstboot

# Add bootstrap puppet code
cat <<-EOF | sudo tee /opt/uib/uib-bootstrap.pp
class { 'puppet':
  server                  => false,
  server_foreman          => false,
  agent                   => true,
  runmode                 => 'none',
  agent_server_hostname   => 'puppetserver04.uib.no',
  ca_server               => 'puppetca.uib.no',
  environment             => 'production',
  client_certname         => \$facts['client_certname']
}
EOF

# Add bootstrap script
cat <<-EOF | sudo tee /opt/uib/uib-bootstrap.sh
#!/bin/bash
# Run puppet on first boot
echo "computeprovider=nrec" > /opt/puppetlabs/facter/facts.d/bootstrap_facts.txt
chmod 600 /opt/puppetlabs/facter/facts.d/bootstrap_facts.txt
# Check if provision.sh has left a firstboot file for us, and remove it when were done bootstrapping
if [ -f /opt/uib/uib-firstboot ]; then
    echo "Running puppet apply with the uib-bootstrap.pp file.
    # Note: This hardcodes the env and role for puppet in our hieradata structure. This might change.
    # Note: Machine name must be unique, not reused, start with p3, below 15 characters (AD/NETBIOS limitation) and not contain slash(-)
    "
    FACTER_client_certname="prod-base-\$(hostname -s)" /opt/puppetlabs/bin/puppet apply /opt/uib/uib-bootstrap.pp

    echo "Running the first puppet run and removing firstboot indicator file"
    FACTER_bootstrap=true /opt/puppetlabs/bin/puppet agent -t
    [[ "$?" != 1 ]] && rm /opt/uib/uib-firstboot # Remove firstboot indicator file if the puppetrun it self didn't fail
fi
EOF
sudo chmod 500 /opt/uib/uib-bootstrap.sh

# Add script for running bootstrap on first run
cat <<-EOF | sudo tee /etc/systemd/system/uib-firstboot.service
[Unit]
Before=systemd-user-sessions.service
Wants=network-online.target
After=network-online.target
ConditionPathExists=/opt/uib/uib-firstboot

[Service]
Type=oneshot
ExecStart=/opt/uib/uib-bootstrap.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl enable uib-firstboot.service
