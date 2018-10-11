#!/bin/bash

# Clear last login info
echo -n "" | sudo tee /var/log/lastlog
echo -n "" | sudo tee /var/log/wtmp
echo -n "" | sudo tee /var/log/btmp

# Just fstrim for now
sudo fstrim / || true
