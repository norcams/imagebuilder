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
    sudo systemctl enable fstrim.timer
    ;;
  "debian")
    if test "$major_version" -ge 8; then
      sudo cp /usr/share/doc/util-linux/examples/fstrim.service /etc/systemd/system
      sudo cp /usr/share/doc/util-linux/examples/fstrim.timer /etc/systemd/system
      sudo systemctl enable fstrim.timer
    else
      printf '#!/bin/sh\nfstrim --all || true\n' | sudo tee /etc/cron.weekly/fstrim
      sudo chmod +x /etc/cron.weekly/fstrim
    fi
    ;;
    # Ubuntu runs fstrim weekly (with anacron) in default install
    "el")
    if test "$major_version" -ge 7; then
      sudo systemctl enable fstrim.timer
    else
      printf '#!/bin/sh\nfstrim --all || true\n' | sudo tee /etc/cron.weekly/fstrim
      sudo chmod +x /etc/cron.weekly/fstrim
    fi
    ;;
esac


