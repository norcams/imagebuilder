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

# Only RHEL 8, 9
case $os_ver in
    8|9|10) ;;
    *)
	echo "This is not a supported RHEL version: os_ver = '$os_ver'"
	exit 0
	;;
esac

# Get a random hex
random_hex=$(openssl rand -hex 8)

# Get and install Satellite certificate
sudo curl -k https://satellite.uio.no/pub/katello-ca-consumer-latest.noarch.rpm \
     -o /tmp/katello-ca-consumer-latest.noarch.rpm
sudo dnf -y --nogpgcheck install /tmp/katello-ca-consumer-latest.noarch.rpm
sudo rm -f /tmp/katello-ca-consumer-latest.noarch.rpm

# Register host
sudo subscription-manager config --server.server_timeout=1800
sudo subscription-manager clean
sudo subscription-manager register --org=UiO --activationkey=satellite --name=nrec-rhel${os_ver}-image-${random_hex}
sudo subscription-manager config --server.server_timeout=180

# Enabling additional repos
case $os_ver in
    9)
	sudo subscription-manager repos \
	     --enable=rhel-9-for-x86_64-supplementary-rpms \
	     --enable=codeready-builder-for-rhel-9-x86_64-rpms
	sudo dnf config-manager --save --setopt=priority=10 \
	     rhel-9-for-x86_64-baseos-rpms \
	     rhel-9-for-x86_64-appstream-rpms \
	     rhel-9-for-x86_64-supplementary-rpms \
	     codeready-builder-for-rhel-9-x86_64-rpms
	;;
    10)
	sudo subscription-manager repos \
	     --enable=rhel-10-for-x86_64-supplementary-rpms \
	     --enable=codeready-builder-for-rhel-10-x86_64-rpms
	sudo dnf config-manager --save --setopt=priority=10 \
	     rhel-10-for-x86_64-baseos-rpms \
	     rhel-10-for-x86_64-appstream-rpms \
	     rhel-10-for-x86_64-supplementary-rpms \
	     codeready-builder-for-rhel-10-x86_64-rpms
	;;

esac

# Installing RHEL GPG keys
sudo rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-redhat-release

# Run katello-rhsm-consumer
sudo katello-rhsm-consumer

# Installing katello-agent
sudo dnf -y install katello-agent

# Upgrading packages
sudo dnf -y upgrade

# Installing UiO dnf repos and GPG key
case $os_ver in
    8)
	sudo dnf -y --nogpgcheck install \
	     http://rpm.uio.no/uio-el8-free/latest/x86_64/Packages/u/uio-release-8-2.el8.noarch.rpm \
	     http://rpm.uio.no/uio-el8-free/latest/x86_64/Packages/u/uio-gpg-keys-0.6-1.el8.noarch.rpm
	sudo rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-uio-el8-free
	;;
    9)
	sudo dnf -y --nogpgcheck install \
	     http://rpm.uio.no/uio-el9-free/latest/x86_64/Packages/u/uio-release-9-4.el9.noarch.rpm \
	     http://rpm.uio.no/uio-el9-free/latest/x86_64/Packages/u/uio-gpg-keys-0.6-1.el9.noarch.rpm
	sudo rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-uio-el9-free
	;;
    10)
	sudo dnf -y --nogpgcheck install \
	     http://rpm.uio.no/uio-el9-free/latest/x86_64/Packages/u/uio-release-10-1.el10.noarch.rpm \
	     http://rpm.uio.no/uio-el9-free/latest/x86_64/Packages/u/uio-gpg-keys-0.6-1.el10.noarch.rpm
	sudo rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-uio-el10-free
	;;
esac

# Installing EPEL dnf repos and GPG key
case $os_ver in
    8)
	sudo dnf -y --nogpgcheck install http://dl.fedoraproject.org/pub/epel/epel-release-latest-8.noarch.rpm
	sudo rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-8
	;;
    9)
	sudo dnf -y --nogpgcheck install http://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm
	sudo rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-9
	;;
    10)
	sudo dnf -y --nogpgcheck install http://dl.fedoraproject.org/pub/epel/epel-release-latest-10.noarch.rpm
	sudo rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-10
	;;
esac

# Marking host as server
sudo mkdir -p /etc/uio/flag
sudo touch /etc/uio/flag/server

# Installing CFEngine
sudo dnf -y install uio-cfengine

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
