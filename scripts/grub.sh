#!/bin/bash

# set path
PATH=/bin:/sbin:/usr/bin:/usr/sbin
export PATH

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

# platform specific files and variables
case $platform in
    'fedora'|'el')
	grub='/etc/default/grub'
	varname='GRUB_CMDLINE_LINUX'
	;;
    'ubuntu')
	grub='/etc/default/grub'
	varname='GRUB_CMDLINE_LINUX_DEFAULT'
	;;
    'debian')
	grub='/etc/default/grub'
	case $major_version in
	    '10')
		varname='GRUB_CMDLINE_LINUX_DEFAULT'
		;;
	    *)
		varname='GRUB_CMDLINE_LINUX'
		;;
	esac
	;;
esac


# set flag if we do changes
flag=0

# we take parameters in whatever variable the distro uses as its main
# kernel command line variable, and store the parameters in an array
# for later use
cmdline=()
eval $(grep $varname $grub | sed -E 's/^GRUB_CMDLINE_LINUX[^[:space:]]*="(.*)"$/foo="\1"/')
for f in $foo; do
    if [[ $f =~ ^(console=|quiet|rhgb|splash) ]]; then
	:
    else
	cmdline+=( $f )
    fi
done

# Comment out GRUB_CMDLINE_LINUX_DEFAULT
#
# Note: Some distros use GRUB_CMDLINE_LINUX_DEFAULT instead of
# GRUB_CMDLINE_LINUX, and its unclear why. The former only applies to
# the default grub selection, while the latter applies to all
sudo sed -i -E 's/^(GRUB_CMDLINE_LINUX_DEFAULT=.*)$/#\1/' $grub

# Set GRUB_CMDLINE_LINUX
if grep -q -E '^GRUB_CMDLINE_LINUX=' $grub; then
    sudo sed -i -E "s%^GRUB_CMDLINE_LINUX=.*$%GRUB_CMDLINE_LINUX=\"console=ttyS0,115200n8 console=tty0 ${cmdline[*]}\"%" $grub
else
    cat <<EOF | sudo tee $grub

# added by NREC 
GRUB_CMDLINE_LINUX="console=ttyS0,115200n8 console=tty0 ${cmdline[*]}"
EOF
fi

# Set GRUB_TIMEOUT
if grep -q -E '^GRUB_TIMEOUT=' $grub; then
    sudo sed -i -E 's/^GRUB_TIMEOUT=.*$/GRUB_TIMEOUT=5/' $grub
else
    cat <<EOF | sudo tee $grub

# added by NREC 
GRUB_TIMEOUT=5
EOF
fi

# Set GRUB_TERMINAL
if grep -q -E '^GRUB_TERMINAL=' $grub; then
    sudo sed -i -E 's/^GRUB_TERMINAL=.*$/GRUB_TERMINAL="serial console"/' $grub
else
    cat <<EOF | sudo tee $grub

# added by NREC 
GRUB_TERMINAL="serial console"
EOF
fi

# Set GRUB_SERIAL_COMMAND
if grep -q -E '^GRUB_SERIAL_COMMAND=' $grub; then
    sudo sed -i -E 's/^GRUB_SERIAL_COMMAND=.*$/GRUB_SERIAL_COMMAND="serial --speed=115200 --unit=0 --word=8 --parity=no --stop=1"/' $grub
else
    cat <<EOF | sudo tee $grub

# added by NREC 
GRUB_SERIAL_COMMAND="serial --speed=115200 --unit=0 --word=8 --parity=no --stop=1"
EOF
fi

# Set GRUB_TIMEOUT_STYLE
if grep -q -E '^GRUB_TIMEOUT_STYLE=' $grub; then
    sudo sed -i -E 's/^GRUB_TIMEOUT_STYLE=.*$/GRUB_TIMEOUT_STYLE=menu/' $grub
else
    cat <<EOF | sudo tee $grub

# added by NREC 
GRUB_TIMEOUT_STYLE=menu
EOF
fi

# Set GRUB_RECORDFAIL_TIMEOUT (only ubuntu)
if [ $platform == 'ubuntu' ]; then
    if grep -q -E '^GRUB_RECORDFAIL_TIMEOUT=' $grub; then
	sudo sed -i -E 's/^GRUB_RECORDFAIL_TIMEOUT=.*$/GRUB_RECORDFAIL_TIMEOUT=0/' $grub
    else
	cat <<EOF | sudo tee $grub

# added by NREC 
GRUB_RECORDFAIL_TIMEOUT=0
EOF
    fi
fi

# Remove timeout override (debian)
if [ -f /etc/default/grub.d/15_timeout.cfg ]; then
    sudo rm -f /etc/default/grub.d/15_timeout.cfg
fi

# Remove cloudimg override (ubuntu)
if [ -f /etc/default/grub.d/50-cloudimg-settings.cfg ]; then
    sudo rm -f /etc/default/grub.d/50-cloudimg-settings.cfg
fi

# update grub.cfg
case $platform in
    'fedora'|'el')
	sudo grub2-mkconfig -o /boot/grub2/grub.cfg
	;;
    'ubuntu'|'debian')
	sudo update-grub
	;;
esac
