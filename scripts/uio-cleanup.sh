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

# Only RHEL 7.x and 8.x
case $os_ver in
    7|8) ;;
    *)
	echo "This is not a supported RHEL version: os_ver = '$os_ver'"
	exit 0
	;;
esac

# Unregister and clean
sudo yum clean all
sudo subscription-manager unregister
sudo subscription-manager clean
sudo rm -f /etc/pki/consumer/*
sudo rm -f /etc/pki/entitlement/*
sudo rm -f /etc/rhsm/facts/katello.facts

# Clean CFEngine, SSHD, Nivlheim
sudo rm -f /var/cfengine/ppkeys/localhost.*
sudo rm -f /etc/ssh/ssh_host_*
sudo rm -f /var/nivlheim/*

# Make NetworkManager update resolv.conf
test -f /etc/NetworkManager/conf.d/99-cloud-init.conf && sudo rm -f /etc/NetworkManager/conf.d/99-cloud-init.conf
