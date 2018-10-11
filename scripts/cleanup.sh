#!/bin/bash

# Clear last login info
>/var/log/lastlog
>/var/log/wtmp
>/var/log/btmp

# Just fstrim for now
sudo fstrim / || true
