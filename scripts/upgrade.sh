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
    sudo sudo dnf upgrade --refresh -y \
    && sudo dnf autoremove -y; \
    sudo dnf clean all
    sudo rm -rf /tmp/*
    ;;
  "debian")
    sudo apt-get update \
    && sudo DEBIAN_FRONTEND=noninteractive apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" upgrade \
    && sudo apt-get autoremove -y; \
    sudo apt-get clean; \
    sudo rm -rf /var/lib/apt/lists/*; \
    sudo rm -rf /tmp/*
    ;;
  "ubuntu")
    sudo apt-get update \
    && sudo DEBIAN_FRONTEND=noninteractive apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" upgrade \
    && sudo apt-get autoremove -y; \
    sudo apt-get clean; \
    sudo rm -rf /var/lib/apt/lists/*; \
    sudo rm -rf /tmp/*
    ;;
  "el")
    sudo yum clean all \
    && sudo yum upgrade -y \
    && sudo yum clean all
    ;;
esac
