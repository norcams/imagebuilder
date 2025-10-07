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

# Unregister and clean
sudo dnf clean all
sudo subscription-manager unregister
sudo subscription-manager clean
sudo sh -c 'rm -f /etc/pki/consumer/*'
sudo sh -c 'rm -f /etc/pki/entitlement/*'
sudo rm -f /etc/rhsm/facts/katello.facts

# Clean CFEngine, Nivlheim
sudo sh -c 'rm -f /var/cfengine/ppkeys/localhost.*'
sudo sh -c 'rm -f /var/nivlheim/*'

# Make NetworkManager update resolv.conf
sudo rm -f /etc/NetworkManager/conf.d/99-cloud-init.conf || :
