## Example usage of imagebuilder

This is tested on Alma Linux 8.8. Beware of a duplicate packer executable in `/usr/sbin`, the correct one is in `/usr/bin`. Modify the order of $PATH to ensure the correct one is used.

### Install

``` bash
<install packer repo> # See Hashicorp Packer documentation
dnf install -y packer gcc python3.11 python3.11-devel
PATH="/usr/bin:$PATH" # Make sure the executable in /usr/bin is used
git clone https://github.com/norcams/imagebuilder imagebuilder
cd imagebuilder/example
python3.11 -m venv .
source bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Build

From the example directory, run:
``` bash
source $HOME/keystore_rc.sh # Make credentials available in ENV. See NREC API documentation for details
./imagebuilder build -n test-image-el8-$(date +%Y-%m-%d) -s $(openstack image show 'GOLD Alma Linux 8' -c id -f value) -a bgo-default-1 -u almalinux -p provision.sh -v --debug
```

### Test build

See `terraform/` for a terraform example to test the image. Edit `main.tf` with image id from build
(and any other changes needed like region, security_group, etc). 

After edit run terraform with ansible inventory output:

``` bash
terraform init
terraform apply
terraform output -raw ansible_inventory_v4
```
