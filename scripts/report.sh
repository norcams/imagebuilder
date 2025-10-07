#!/bin/bash

# Get OS info
test -f /etc/os-release && . /etc/os-release
os_id=$ID
os_ver=$(echo $VERSION_ID | cut -d. -f1)

# Avoid RHEL
if [ "$os_id" == 'rhel' ]; then
    echo "report.sh not applicable for $os_id"
    exit 0
fi

install_wrapper() {
    cat <<-EOF | sudo tee /usr/local/sbin/report_wrapper
#!/bin/bash
set -e

$download_cmd $url
chmod +x /usr/local/sbin/report

/usr/local/sbin/report

exit 0
EOF
    sudo chmod +x /usr/local/sbin/report_wrapper
}

install_anacron() {
    cat <<-EOF | sudo tee /etc/cron.daily/report
#!/bin/sh

/usr/local/sbin/report_wrapper &> /dev/null

exit 0
EOF
    sudo chmod 700 /etc/cron.daily/report
}

install_systemd() {
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
Description=Report to NREC report API

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/report_wrapper
EOF
    sudo systemctl enable report.timer
}

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

url="https://report.nrec.no/downloads/${platform}/${major_version}/v1/report"

case $platform in
    "debian")
	download_cmd='wget --quiet -O /usr/local/sbin/report'
	install_wrapper
	install_systemd
	;;
    *)
	download_cmd='curl -fsS -o /usr/local/sbin/report'
	install_wrapper
	install_systemd
	;;
esac
