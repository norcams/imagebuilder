#!/bin/bash

# Set proper PATH
PATH=/usr/bin:/usr/sbin
export PATH

# Get OS info
test -f /etc/os-release && . /etc/os-release

os_id=$ID
os_ver=$(echo $VERSION_ID | cut -d. -f1)

# Only RHEL
if [ "$os_id" != 'rhel' ]; then
    echo "Not applicable: os_id = '$os_id'"
    exit 0
fi

# Only RHEL 7, 8, 9
case $os_ver in
    7|8|9) ;;
    *)
	echo "This is not a supported RHEL version: os_ver = '$os_ver'"
	exit 0
	;;
esac

# Get a random hex
random_hex=$(openssl rand -hex 8)

# Get and install Satellite certificate
sudo curl -k https://satellite.uio.no/pub/katello-ca-consumer-latest.noarch.rpm -o /tmp/katello-ca-consumer-latest.noarch.rpm
sudo yum -y --nogpgcheck install /tmp/katello-ca-consumer-latest.noarch.rpm
sudo rm -f /tmp/katello-ca-consumer-latest.noarch.rpm

# Register host
sudo subscription-manager config --server.server_timeout=1800
sudo subscription-manager clean
sudo subscription-manager register --org=UiO --activationkey=satellite --name=nrec-rhel${os_ver}-image-${random_hex}
sudo subscription-manager config --server.server_timeout=180

# Enabling additional repos
case $os_ver in
    9)
	sudo subscription-manager repos --enable=rhel-9-for-x86_64-supplementary-rpms
	sudo subscription-manager repos --enable=codeready-builder-for-rhel-9-x86_64-rpms
	;;
esac

# Installing RHEL GPG keys
sudo rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-redhat-release

# Install yum-plugin-priorities
sudo yum -y install yum-plugin-priorities

# Run katello-rhsm-consumer
sudo katello-rhsm-consumer

# Installing katello-agent
sudo yum -y install katello-agent

# Upgrading packages
sudo yum -y upgrade

# Installing UiO yum repos and GPG key
case $os_ver in
    7)
	sudo yum -y --nogpgcheck install http://rpm.uio.no/uio-el7-free/latest/x86_64/Packages/u/uio-release-7-2.noarch.rpm
	sudo rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-UIO
	;;
    8)
	sudo yum -y --nogpgcheck install http://rpm.uio.no/uio-el8-free/latest/x86_64/Packages/u/uio-release-8-1.el8.noarch.rpm
	sudo rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-uio-el8-free
	;;
    9)
	sudo yum -y --nogpgcheck install http://rpm.uio.no/uio-el9-free/latest/x86_64/Packages/u/uio-release-9-2.el9.noarch.rpm
	sudo rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-uio-el9-free
	;;
esac

# Installing EPEL yum repos and GPG key
case $os_ver in
    7)
	sudo yum -y --nogpgcheck install http://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm
	sudo rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-7
	;;
    8)
	sudo yum -y --nogpgcheck install http://dl.fedoraproject.org/pub/epel/epel-release-latest-8.noarch.rpm
	sudo rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-8
	;;
    9)
	sudo yum -y --nogpgcheck install http://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm
	sudo rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-9
	;;
esac

# Marking host as server
sudo mkdir -p /etc/uio/flag
sudo touch /etc/uio/flag/server

# Installing CFEngine
sudo yum -y install uio-cfengine

# Initializing CFEngine
sudo mkdir -p /var/cfengine/bin
sudo mkdir -p /var/cfengine/ppkeys
sudo mkdir -p /var/cfengine/inputs
sudo chmod 700 /var/cfengine/ppkeys
sudo cp -f /opt/cfengine/sbin/cf-agent /var/cfengine/bin
sudo cp -f /opt/cfengine/sbin/cf-key /var/cfengine/bin
sudo cp -f /opt/cfengine/sbin/cf-promises /var/cfengine/bin
sudo cp -f /opt/cfengine/inputs/failsafe.cf /var/cfengine/inputs
sudo /var/cfengine/bin/cf-key
sudo /var/cfengine/bin/cf-agent -f /var/cfengine/inputs/failsafe.cf
sudo /var/cfengine/bin/cf-agent -K -Danaconda
sudo /var/cfengine/bin/cf-agent -K -Danaconda

# Removing CFEngine rpm state file
if [ -f /var/cfengine/state/software_packages.csv ]; then
    sudo rm -f /var/cfengine/state/software_packages.csv
fi

# Turning on sssd
sudo systemctl enable sssd.service

# Running cf-agent one last time
sudo /var/cfengine/bin/cf-agent -K -Danaconda

# Fixing SELinux labels
sudo restorecon -R /var /etc /root

# Cloud-init: Red Hat Subscription
cat <<-EOF | sudo tee /etc/cloud/cloud.cfg.d/10_rh_subscription.cfg
rh_subscription:
    activation-key: satellite
    org: UiO
    auto-attach: true
EOF

# Cloud-init: Time zone
cat <<-EOF | sudo tee /etc/cloud/cloud.cfg.d/15_timezone.cfg
timezone: Europe/Oslo
EOF
