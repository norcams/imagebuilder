#!/bin/bash
# Platform detection (borrowed from Omnitruck install script)
# Debian-family and RedHat-family are currently supported
# FIXME move platform detection to seperate file, use env var
os=`uname -s | tr '[A-Z]' '[a-z]'`

if test -f "/etc/lsb-release" && grep -q DISTRIB_ID /etc/lsb-release && ! grep -q wrlinux /etc/lsb-release; then
    platform=`grep DISTRIB_ID /etc/lsb-release | cut -d "=" -f 2 | tr '[A-Z]' '[a-z]'`
    platform_version=`grep DISTRIB_RELEASE /etc/lsb-release | cut -d "=" -f 2`

elif test -f "/etc/debian_version"; then
    platform="debian"
    platform_version=`cat /etc/debian_version`

elif test -f "/etc/redhat-release"; then
    platform=`sed 's/^\(.\+\) release.*/\1/' /etc/redhat-release | tr '[A-Z]' '[a-z]'`
    platform_version=`sed 's/^.\+ release \([.0-9]\+\).*/\1/' /etc/redhat-release`

    # If /etc/redhat-release exists, we act like RHEL by default
    if test "$platform" != "fedora"; then
	platform="el"
    fi
fi

if test "x$platform" = "x"; then
    echo "Unable to determine platform version!"
    exit 0
fi

major_version=`echo $platform_version | cut -d. -f1`

case $platform in
    "fedora")
	cat <<-EOF | sudo tee /etc/cloud/cloud.cfg.d/custom-networking.cfg
network:
  version: 2
  ethernets:
  # opaque ID for physical interfaces, only referred to by other stanzas
    local_if:
      match:
        name: e*
      accept-ra: true
      dhcp6: true
      dhcp4: true
EOF
	;;
    "debian")
	case $major_version in
	    "11")
		cat <<-EOF | sudo tee /etc/cloud/cloud.cfg.d/custom-networking.cfg
network:
  version: 1
  config:
  - type: physical
    name: enp3s0
    subnets:
      - type: dhcp
      - type: dhcp6
EOF
		;;
	    "12"|"13")
		cat <<-EOF | sudo tee /etc/cloud/cloud.cfg.d/custom-networking.cfg
network:
  version: 2
  ethernets:
  # opaque ID for physical interfaces, only referred to by other stanzas
    local_if:
      match:
        name: e*
      accept-ra: true
      dhcp6: true
      dhcp4: true
EOF
		;;
	esac
	;;
    "ubuntu")
	cat <<-EOF | sudo tee /etc/cloud/cloud.cfg.d/custom-networking.cfg
network:
  version: 2
  ethernets:
  # opaque ID for physical interfaces, only referred to by other stanzas
    local_if:
      match:
        name: e*
      accept-ra: true
      dhcp6: true
      dhcp4: true
EOF
	;;
    "el")
	cat <<-EOF | sudo tee /etc/cloud/cloud.cfg.d/custom-networking.cfg
network:
  version: 2
  ethernets:
  # opaque ID for physical interfaces, only referred to by other stanzas
    local_if:
      match:
        name: e*
      accept-ra: true
      dhcp6: true
      dhcp4: true
EOF
	;;
esac
