#!/bin/bash
#
# Install Quemu Guest agent in the image and set required image properties
#

# Find distribution and major version
# Platform detection borrowed from Omnitruck install script
# Debian-family and RedHat-family are currently supported

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
    # The agent is installed by default
    sudo systemctl enable qemu-guest-agent.service
    sudo dnf clean all
    ;;
  "el")
    case $major_version in
      "6")
        # We don't support RHEL 6 for this
        ;;
      "7"|"8")
        # The agent is installed by default
        sudo systemctl enable qemu-guest-agent.service
        sudo yum clean all
        ;;
    esac
    ;;
  "debian")
    sudo apt-get update \
    && sudo DEBIAN_FRONTEND=noninteractive apt-get install qemu-guest-agent -y
    # agent is vendor enabled on Debian
    sudo apt-get clean
    ;;
  "ubuntu")
    sudo apt-get update \
    && sudo DEBIAN_FRONTEND=noninteractive apt-get install qemu-guest-agent -y
    # agent is vendor enabled on Debian
    sudo apt-get clean
    ;;
esac
