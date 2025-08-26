#!/bin/bash

# Enable X-forwarding
apt update
apt install -y xauth
sed -i 's/^X11Forwarding /#&/' /etc/ssh/sshd_config
sed -i 's/^UsePAM /#&/' /etc/ssh/sshd_config
sed -i 's/^KbdInteractiveAuthentication /#&/' /etc/ssh/sshd_config

cat <<EOF >> /etc/ssh/sshd_config
X11Forwarding yes
UsePAM yes
KbdInteractiveAuthentication yes
EOF

# Create alias for Firefox to work in X-forwarding
echo 'alias firefox="XAUTHORITY=$HOME/.Xauthority /snap/bin/firefox"' | sudo tee /etc/profile.d/firefox_alias.sh
sudo chmod +x /etc/profile.d/firefox_alias.sh

# Delete default user on first boot
cat <<- EOF > /etc/systemd/system/delete-ubuntu-user.service
[Unit]
Description=Delete the default user "ubuntu"

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'if id "ubuntu" &>/dev/null; then userdel -r ubuntu; fi'
RemainAfterExit=true

[Install]
WantedBy=multi-user.target
EOF
#systemctl enable delete-ubuntu-user.service

# Install and prepare authd with EntraID
add-apt-repository -y ppa:ubuntu-enterprise-desktop/authd
apt update
apt install -y authd gnome-shell yaru-theme-gnome-shell
snap install authd-msentraid
mkdir -p /etc/authd/brokers.d/
cp /snap/authd-msentraid/current/conf/authd/msentraid.conf /etc/authd/brokers.d/

# Configure EntraID
BROKER_CONF=/var/snap/authd-msentraid/current/broker.conf
sed -i 's|issuer = https://login.microsoftonline.com/<ISSUER_ID>/v2.0|issuer = https://login.microsoftonline.com/$TENANT_ID/v2.0|' $BROKER_CONF
sed -i 's|client_id = <CLIENT_ID>|client_id = $CLIENT_ID|' $BROKER_CONF
sed -i 's|#allowed_users = OWNER|allowed_users = ALL|' $BROKER_CONF

# Set appropiate login timeout (default is too short for EntraID logins)
sed -i 's|LOGIN_TIMEOUT[[:space:]]*[0-9]*|LOGIN_TIMEOUT           360|' /etc/login.defs
