#!/bin/bash
# Platform detection (borrowed from Omnitruck install script)
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

url="https://report.uh-iaas.no/downloads/${platform}/${major_version}/report"

install() {
cat <<-EOF | sudo tee /usr/local/sbin/report_wrapper
#!/bin/bash
set -e

curl -fsS $url -o /usr/local/sbin/report
chmod +x /usr/local/sbin/report

/usr/local/sbin/report

exit 0
EOF
  sudo chmod +x /usr/local/sbin/report_wrapper
cat <<-EOF | sudo tee /lib/systemd/system/report.timer
[Unit]
Description=Run report script every 6h and on boot

[Timer]
OnBootSec=15min
OnUnitActiveSec=12h
Persistent=true

[Install]
WantedBy=timers.target
EOF
cat <<-EOF | sudo tee /lib/systemd/system/report.service
[Unit]
Description=Report to UH-IaaS report API

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/report_wrapper
EOF
  sudo systemctl enable report.timer
}

case $platform in
  "el")
    case $major_version in
      "6")
        break
        ;;
      "7")
        install
        ;;
    esac
    ;;
  *)
    install
    ;;
esac
