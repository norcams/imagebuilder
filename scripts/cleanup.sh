#!/bin/bash

# Clear last login info
echo -n "" | sudo tee /var/log/lastlog
echo -n "" | sudo tee /var/log/wtmp
echo -n "" | sudo tee /var/log/btmp

# Trigger systemd-firstboot, ensure unique machine-id
if [ -f /etc/machine-id ]; then
    echo -n "" | sudo tee /etc/machine-id
fi
if [ -f /var/lib/dbus/machine-id ]; then
    echo -n "" | sudo tee /var/lib/dbus/machine-id
fi

# Just fstrim for now
sudo fstrim / || true
