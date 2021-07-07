#!/bin/bash
#
# Install NVIDIA Grid driver for virtual GPU
#
# Tested for Ubuntu 20.04, Centos 7.x/8.x
# May work on other distros like Fedora and Debian
#

# Be verbose, disallow unset variables and exit on error
set -x
set -u
set -e

# Set license server based on region for the running instance
if grep -q -ir 'bgo-default' /run/cloud-init/; then
    licserver='lisens8.uib.no'
    backup_licserver=''
elif grep -q -ir 'osl-default' /run/cloud-init/; then
    licserver='lisens-nvidia-01.uio.no'
    backup_licserver='lisens-nvidia-02.uio.no'
else
    licserver='placeholder.example.com'
    backup_licserver=''
fi

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
fi

if [ "x$platform" = "x" ]; then
    echo "Unable to determine platform version!"
    exit 1
fi

major_version=$(echo $platform_version | cut -d. -f1)

# The nouveau driver needs to be blacklisted
sudo sh -c "printf 'blacklist nouveau\noptions nouveau modeset=0\n' > /etc/modprobe.d/blacklist-nvidia-nouveau.conf"
case $platform in
    "fedora")
	sudo /usr/bin/dracut --force
	;;
    "el")
	case $major_version in
	    "7")
		sudo /sbin/dracut --force
		;;
	    "8")
		sudo /usr/bin/dracut --force
		;;
	esac
	;;
    "debian"|"ubuntu")
	sudo /usr/sbin/update-initramfs -u
	;;
esac

# Install dkms and pciutils. Then determine newest installed kernel
case $platform in
    "fedora")
	sudo /usr/bin/dnf install -y pciutils dkms kernel-devel kernel-headers
	sudo /usr/bin/dnf update -y kernel kernel-devel kernel-headers
	KERNELINSTALLED=$(rpm -qa kernel | sort -V -r | head -n 1)
	KERNELVERSION=${KERNELINSTALLED##kernel-}
	;;
    "el")
	case $major_version in
	    "7")
		sudo /bin/yum install -y pciutils epel-release
		sudo /bin/yum install -y dkms kernel-devel kernel-headers
		sudo /bin/yum update -y kernel kernel-devel kernel-headers
		KERNELINSTALLED=$(rpm -qa kernel | sort -V -r | head -n 1)
		KERNELVERSION=${KERNELINSTALLED##kernel-}
		;;
	    "8")
		sudo /usr/bin/dnf install -y pciutils epel-release
		sudo /usr/bin/dnf install -y dkms kernel-devel kernel-headers
		sudo /usr/bin/dnf update -y kernel kernel-devel kernel-headers
		KERNELINSTALLED=$(rpm -qa kernel | sort -V -r | head -n 1)
		KERNELVERSION=${KERNELINSTALLED##kernel-}
		;;
	esac
	;;
    "debian")
	sudo /usr/bin/apt-get update -y
	sudo /usr/bin/apt-get dist-upgrade -y
	sudo /usr/bin/apt -y install dkms pciutils curl
	KERNELINSTALLED=$(/usr/bin/dpkg --list | grep linux-image | grep -v meta-package | sort -V -r | head -n 1 | cut -d' ' -f3)
	KERNELVERSION=${KERNELINSTALLED##linux-image-}
	sudo /usr/bin/apt install -y linux-headers-$KERNELVERSION
	;;
    "ubuntu")
	sudo /usr/bin/apt-get update -y
	sudo /usr/bin/apt-get dist-upgrade -y
	sudo /usr/bin/apt -y install dkms pciutils
	KERNELINSTALLED=$(/usr/bin/dpkg --list | grep linux-image | grep generic | sort -V -r | head -n 1 | cut -d' ' -f3)
	KERNELVERSION=${KERNELINSTALLED##linux-image-}
	sudo /usr/bin/apt install -y linux-headers-$KERNELVERSION
	;;
esac

# Get latest NVIDIA GRID package and build with dkms for newest installed kernel
cd /tmp
/usr/bin/curl -O https://download.iaas.uio.no/nrec/nrec-resources/files/nvidia-vgpu/linux-grid-latest
chmod +x linux-grid-latest
sudo ./linux-grid-latest --dkms -n -s -k $KERNELVERSION

# Configure license server for the GRID software based on region
cd /etc/nvidia
sudo cp gridd.conf.template gridd.conf
sudo sed -i "s/^ServerAddress=/ServerAddress=$licserver/" gridd.conf
if [ "x${backup_licserver}" != "x" ]; then
    sudo sed -i "s/^#BackupServerAddress=/BackupServerAddress=$backup_licserver/" gridd.conf
fi

# Clean up the driver package
cd /tmp
/bin/rm -f ./linux-grid-latest
