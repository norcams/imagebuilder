#!/bin/bash
# Clear last login info
echo -n "" | sudo tee /var/log/lastlog
echo -n "" | sudo tee /var/log/wtmp
echo -n "" | sudo tee /var/log/btmp
echo -n "" | sudo tee /var/log/cloud-init.log
echo -n "" | sudo tee /var/log/cloud-init-output.log

# Trigger systemd-firstboot, ensure unique machine-id
if [ -f /etc/machine-id ]; then
    echo -n "" | sudo tee /etc/machine-id
fi
if [ -f /var/lib/dbus/machine-id ]; then
    echo -n "" | sudo tee /var/lib/dbus/machine-id
fi

# Remove ssh host keys
sudo sh -c 'rm -f /etc/ssh/ssh_host_*'

# Just fstrim for now
sudo fstrim / || true

# Clean up authorized_keys
: > ~/.ssh/authorized_keys
sudo bash -c ': > /root/.ssh/authorized_keys'

# Remove logs and artifacts so cloud-init can re-run
sudo cloud-init clean
