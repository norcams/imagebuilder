#!/bin/bash
#
# Install NVIDIA Grid driver for virtual GPU
#
# Tested for Ubuntu 20.04, Centos 7.x/8.x
# May work on other distros like Fedora and Debian
#

# Set license server based on region for the running instance
if $(grep -ir bgo-default /run/cloud-init/ &>/dev/null); then licserver=lisens8.uib.no; fi
if $(grep -ir osl-default /run/cloud-init/ &>/dev/null); then licserver=placeholder.example.com; fi

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

# The nouveau driver needs to be blacklisted
printf 'blacklist nouveau\noptions nouveau modeset=0\n' > /etc/modprobe.d/blacklist-nvidia-nouveau.conf
case $platform in
  "fedora")
    /usr/bin/dracut --force
    ;;
  "el")
    case $major_version in
      "7")
        /sbin/dracut --force
        ;;
      "8")
        /usr/bin/dracut --force
        ;;
    esac
    ;;
  "debian"|"ubuntu")
    /usr/sbin/update-initramfs -u
    ;;
esac

# Install dkms and pciutils. Then determine newest installed kernel
case $platform in
  "fedora")
    /usr/bin/dnf install -y pciutils dkms kernel-devel kernel-headers
    /usr/bin/dnf update -y kernel kernel-devel kernel-headers
    KERNELINSTALLED=$(rpm -qa kernel | sort -V -r | head -n 1)
    KERNELVERSION=${KERNELINSTALLED##kernel-}
    ;;
  "el")
    case $major_version in
      "7")
        /bin/yum install -y pciutils epel-release
        /bin/yum install -y dkms kernel-devel kernel-headers
        /bin/yum update -y kernel kernel-devel kernel-headers
        KERNELINSTALLED=$(rpm -qa kernel | sort -V -r | head -n 1)
        KERNELVERSION=${KERNELINSTALLED##kernel-}
        ;;
      "8")
        /usr/bin/dnf install -y pciutils epel-release
        /usr/bin/dnf install -y dkms kernel-devel kernel-headers
        /usr/bin/dnf update -y kernel kernel-devel kernel-headers
        KERNELINSTALLED=$(rpm -qa kernel | sort -V -r | head -n 1)
        KERNELVERSION=${KERNELINSTALLED##kernel-}
        ;;
    esac
    ;;
  "debian")
    /usr/bin/apt -y install dkms pciutils curl
    /usr/bin/apt-get update -y
    /usr/bin/apt-get dist-upgrade -y
    KERNELINSTALLED=$(/usr/bin/dpkg --list | grep linux-image | grep -v meta-package | sort -V -r | head -n 1 | cut -d' ' -f3)
    KERNELVERSION=${KERNELINSTALLED##linux-image-}
    /usr/bin/apt install -y linux-headers-$KERNELVERSION
    ;;
  "ubuntu")
    /usr/bin/apt -y install dkms pciutils
    /usr/bin/apt-get update -y
    /usr/bin/apt-get dist-upgrade -y
    KERNELINSTALLED=$(/usr/bin/dpkg --list | grep linux-image | grep generic | sort -V -r | head -n 1 | cut -d' ' -f3)
    KERNELVERSION=${KERNELINSTALLED##linux-image-}
    /usr/bin/apt install -y linux-headers-$KERNELVERSION
    ;;
esac

# Get latest NVIDIA GRID package and build with dkms for newest installed kernel
cd /root
/usr/bin/curl -O https://iaas-repo.uio.no/uh-iaas/nrec-resources/files/nvidia-vgpu/linux-grid-latest
chmod +x linux-grid-latest
./linux-grid-latest --dkms -n -s -k $KERNELVERSION

# Configure license server for the GRID software based on region
cd /etc/nvidia/
cp gridd.conf.template gridd.conf
sed -i "s/^ServerAddress=/ServerAddress=$licserver/" gridd.conf

# Clean up the driver package
cd /root
/bin/rm -rf ./linux-grid-latest
