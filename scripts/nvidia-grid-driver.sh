#!/bin/bash
#
# Install NVIDIA Grid driver for virtual GPU
#
# Tested for Ubuntu 20.04, Centos 7.x/8.x
# May work on other distros like Fedora and Debian
#

# Set PATH
export PATH=/usr/bin:/bin:/usr/sbin:/sbin

# Be verbose, disallow unset variables and exit on error
set -x
set -u
set -e

# Find distribution and major version
# Platform detection borrowed from Omnitruck install script
# Debian-family and RedHat-family are currently supported
os=$(uname -s | tr '[A-Z]' '[a-z]')

if [ -f "/etc/lsb-release" ] && grep -q DISTRIB_ID /etc/lsb-release && ! grep -q wrlinux /etc/lsb-release; then
    platform=$(grep DISTRIB_ID /etc/lsb-release | cut -d "=" -f 2 | tr '[A-Z]' '[a-z]')
    platform_version=$(grep DISTRIB_RELEASE /etc/lsb-release | cut -d "=" -f 2)
elif [ -f "/etc/debian_version" ]; then
    platform="debian"
    platform_version=$(cat /etc/debian_version)
elif [ -f "/etc/redhat-release" ]; then
    platform=$(sed 's/^\(.\+\) release.*/\1/' /etc/redhat-release | tr '[A-Z]' '[a-z]')
    platform_version=$(sed 's/^.\+ release \([.0-9]\+\).*/\1/' /etc/redhat-release)

    # If /etc/redhat-release exists, we act like RHEL by default
    if [ "$platform" != "fedora" ]; then
	platform="el"
    fi
fi

if [ "x$platform" = "x" ]; then
    echo "Unable to determine platform version!"
    exit 1
fi

major_version=$(echo $platform_version | cut -d. -f1)

# The nouveau driver needs to be blacklisted
sudo sh -c "printf 'blacklist nouveau\noptions nouveau modeset=0\n' > /etc/modprobe.d/blacklist-nvidia-nouveau.conf"
case $platform in
    'fedora'|'el')
	sudo dracut --force
	;;
    'debian'|'ubuntu')
	sudo update-initramfs -u
	;;
esac

# Install dkms and pciutils. Then determine newest installed kernel
case $platform in
    'fedora')
	sudo dnf install -y pciutils dkms kernel-devel kernel-headers
	sudo dnf upgrade -y kernel kernel-devel kernel-headers
	KERNELVERSION=$(sudo grubby --default-kernel | sed 's|/boot/vmlinuz-||')
	;;
    'el')
	sudo yum install -y pciutils epel-release
	sudo yum install -y dkms kernel-devel kernel-headers
	sudo yum upgrade -y kernel kernel-devel kernel-headers
	KERNELVERSION=$(sudo grubby --default-kernel | sed 's|/boot/vmlinuz-||')
	;;
    'debian')
	sudo apt-get update -y
	sudo apt-get dist-upgrade -y
	sudo apt -y install dkms pciutils curl
	KERNELINSTALLED=$(dpkg --list | grep linux-image | grep -v meta-package | sort -V -r | head -n 1 | cut -d' ' -f3)
	KERNELVERSION=${KERNELINSTALLED##linux-image-}
	sudo apt install -y linux-headers-$KERNELVERSION
	;;
    'ubuntu')
	sudo apt-get update -y
	sudo DEBIAN_FRONTEND=noninteractive apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" upgrade
	sudo DEBIAN_FRONTEND=noninteractive apt -y install dkms pciutils
	KERNELINSTALLED=$(dpkg --list | grep linux-image | grep generic | sort -V -r | head -n 1 | cut -d' ' -f3)
	KERNELVERSION=${KERNELINSTALLED##linux-image-}
	sudo apt install -y linux-headers-$KERNELVERSION
	;;
esac

# Get latest NVIDIA GRID package and build with dkms for newest installed kernel
cd /tmp
curl -O https://download.iaas.uio.no/nrec/nrec-resources/files/nvidia-vgpu/linux-grid-latest
chmod +x linux-grid-latest
sudo ./linux-grid-latest --dkms --no-drm -n -s -k $KERNELVERSION

# Configure gridd.conf and licensing based on region
if sudo grep -q -ir 'bgo-default' /run/cloud-init/; then
    sudo curl -s https://download.iaas.uio.no/nrec/nrec-resources/files/nvidia-vgpu/gridd.conf-BGO -o /etc/nvidia/gridd.conf
elif sudo grep -q -ir 'osl-default' /run/cloud-init/; then
    sudo curl -s https://download.iaas.uio.no/nrec/nrec-resources/files/nvidia-vgpu/gridd.conf-OSL -o /etc/nvidia/gridd.conf
    sudo mkdir -p /etc/nvidia/ClientConfigToken
    sudo curl -s https://download.iaas.uio.no/nrec/nrec-resources/files/nvidia-vgpu/client_configuration_token_01-30-2023-12-20-51.tok -s -o /etc/nvidia/ClientConfigToken/client_configuration_token_01-30-2023-12-20-51.tok
else
    sudo curl -s https://download.iaas.uio.no/nrec/nrec-resources/files/nvidia-vgpu/gridd.conf-default -o /etc/nvidia/gridd.conf
fi

# Clean up the driver package
cd /tmp
rm -f ./linux-grid-latest
