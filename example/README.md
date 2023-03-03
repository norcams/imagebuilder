## Example usage of imagebuilder

This is tested on Alma Linux 8.7

### Install

``` bash
<install packer repo>
dnf install -y packer python3-virtualenv python39
cd <clone>
virtualenv-3 -p /usr/bin/python3.9 .
source bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Build

``` bash
imagebuilder build -n test-image-el8-$(date +%Y-%m-%d) -s $(openstack image show 'GOLD Alma Linux 8' -c id -f value) -a bgo-default-1 -u almalinux -p provision.sh -v --debug
```
