#!/bin/bash

# Set proper PATH
PATH=/usr/bin:/usr/sbin
export PATH

# Variables
SSHD_CONF=/etc/ssh/sshd_config
SSHD_TMP=$(mktemp)

# Add desired hardening block, creating temporary file
sudo awk '
{ print }
/#ListenAddress ::/ {
    print ""
    print "# Host Keys [NREC]"
    print "HostKey /etc/ssh/ssh_host_rsa_key"
    print "HostKey /etc/ssh/ssh_host_ed25519_key"
    print ""
    print "# OpenSSH hardening [NREC]"
    print "KexAlgorithms curve25519-sha256@libssh.org,diffie-hellman-group-exchange-sha256"
    print "Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com,aes128-gcm@openssh.com,aes256-ctr,aes128-ctr"
    print "MACs hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com,umac-128-etm@openssh.com,hmac-sha2-512,hmac-sha2-256,umac-128@openssh.com"
    print "HostkeyAlgorithms ssh-ed25519,ssh-rsa"
}
' $SSHD_CONF > $SSHD_TMP

# Replace with edited file
sudo cp -f $SSHD_TMP $SSHD_CONF

# Remove temporary file
sudo rm -f $SSHD_TMP
