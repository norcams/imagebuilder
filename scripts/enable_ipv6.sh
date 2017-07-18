#!/bin/sh
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
    sudo echo "NETWORKING_IPV6=\"yes\"" >> /etc/sysconfig/network \
    && sudo sed -i '/IPV6INIT="no"/d' /etc/sysconfig/network-scripts/ifcfg-eth0 \
    && sudo echo -e "IPV6INIT=\"yes\"\nDHCPV6C=\"yes\"" >> /etc/sysconfig/network-scripts/ifcfg-eth0
    ;;
  "debian")
    sudo echo "timeout 10;" >> /etc/dhcp/dhclient6.conf \
    && sudo echo -e "iface eth0 inet6 auto\n    up sleep 5\n    up dhclient -1 -6 -cf /etc/dhcp/dhclient6.conf -lf /var/lib/dhcp/dhclient6.eth0.leases -v eth0 || true" >> /etc/network/interfaces
    ;;
  "ubuntu")
    # Try to figure out interface by looking at routing table
    if=`route | grep '^default' | grep -o '[^ ]*$'`
    sudo echo "timeout 10;" >> /etc/dhcp/dhclient6.conf \
    && sudo echo -e "iface ${if} inet6 auto\n    up sleep 5\n    up dhclient -1 -6 -cf /etc/dhcp/dhclient6.conf -lf /var/lib/dhcp/dhclient6.${if}.leases -v ${if} || true" >> /etc/network/interfaces.d/50-cloud-init.cfg
    ;;
  "el")
    sudo echo "NETWORKING_IPV6=\"yes\"" >> /etc/sysconfig/network \
    && sudo sed -i '/IPV6INIT="no"/d' /etc/sysconfig/network-scripts/ifcfg-eth0 \
    && sudo echo -e "IPV6INIT=\"yes\"\nDHCPV6C=\"yes\"" >> /etc/sysconfig/network-scripts/ifcfg-eth0
    ;;
esac
