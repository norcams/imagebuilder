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
    sudo dnf install dnf-automatic -y \
    && sudo sed -i -e 's/apply_updates = no/apply_updates = yes/g' /etc/dnf/automatic.conf \
    && sudo systemctl enable dnf-automatic.timer
    sudo dnf clean all
    sudo rm -rf /tmp/*
    ;;
  "el")
    case $major_version in
      "6")
        sudo yum install yum-cron -y \
        && sudo chkconfig yum-cron on
        sudo yum clean all
        ;;
      "7")
        sudo yum install yum-cron -y \
        && sudo sed -i -e 's/apply_updates = no/apply_updates = yes/g' /etc/yum/yum-cron.conf \
        && sudo systemctl enable yum-cron.service
        sudo yum clean all
        ;;
      "8")
        sudo dnf install dnf-automatic -y \
        && sudo sed -i -e 's/apply_updates = no/apply_updates = yes/g' /etc/dnf/automatic.conf \
        && sudo systemctl enable --now dnf-automatic.timer
        sudo dnf clean all
        ;;
    esac
    ;;
  "debian")
    sudo apt-get update \
    && sudo apt-get install unattended-upgrades apt-listchanges -y \
    && sudo sed -i -e 's/"0"/"1"/' /etc/apt/apt.conf.d/20auto-upgrades
    sudo apt-get clean
    sudo rm -rf /var/lib/apt/lists/*
    sudo rm -rf /tmp/*
    ;;
  "ubuntu")
    sudo apt-get update \
    && sudo apt-get install unattended-upgrades apt-listchanges -y \
    && sudo sed -i -e 's/"0"/"1"/' /etc/apt/apt.conf.d/20auto-upgrades
    sudo apt-get clean
    sudo rm -rf /var/lib/apt/lists/*
    sudo rm -rf /tmp/*
    ;;
esac
