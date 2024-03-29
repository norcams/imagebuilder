# imagebuilder

Image Builder for [NREC](https://www.nrec.no)

imagebuilder is a Command Line Interface for building fully provisioned,
ready-to-use images/snapshots in NREC using [Packer](https://packer.io).

It's basically just a wrapper for Packer doing the necessary steps required to
make Packer work with NREC default configurations, and without the need to
make or edit templates.

imagebuilder is meant to simplify the process of making and automate the
buildling of machine images in NREC using only the command-line. For more
advanced image building you should learn [how to use
Packer](https://www.packer.io/docs/).

Pull requests are welcome!

### Requirements
* Python 3
* [keystoneauth](https://github.com/openstack/keystoneauth)
* [python-novaclient](https://github.com/openstack/python-novaclient)
* [python-glanceclient](https://github.com/openstack/python-glanceclient)
* [Packer](https://packer.io)
* OpenSSL command line tool


### Installation
- Clone this repository `git clone https://github.com/norcams/imagebuilder`
- Install the requirements `pip3 install -r requirements.txt`
- Run `./imagebuilder`

Note that if you're running RHEL/CentOS there is another tool named packer in
the default installation, unrelated to the Packer being used by imagebuilder.
Check your user's $PATH to make sure the correct Packer is being executed.

### Usage
Create a keystone_rc.sh file if you haven't already as described in
[this document](http://docs.uh-iaas.no/en/latest/api.html)

Source this file: `source keystone_rc.sh`

An example build command could be:

`imagebuilder build -n my_image -s 90be98a5-0883-4a15-9006-2e012f9802d4 -a osl-default-1 -u centos -p my_provision_script.sh -d`

where -n is the name of the image, -s is the id of a source image, -a is
the availability zone, -u is the SSH user created by cloud-init for your source
image of choice (i.e. centos, ubuntu), -p is the path to your provision script
and -d downloads the image after it's been built. 

imagebuilder creates a temporary security group and keypair named
"imagebuilder-<UUID>" which will be deleted after completion. Note that you for
now will have to delete these manually if the command is not allowed to finish. 

Run `imagebuilder <command> -h` for a complete list of options. 

### Bootstrap

You can use imagebuilder to download a cloud-ready image from a URL and upload
it to Glance (Openstack's image service).

An example bootstrap command could be:

`imagebuilder bootstrap -n 'IMAGEBUILDER CentOS 7' -a bgo-default-1 -u http://cloud.centos.org/centos/7/images/CentOS-7-x86_64-GenericCloud.qcow2 -c http://cloud.centos.org/centos/7/images/sha256sum.txt -t sha256 -r 768 -d 8 -f qcow2` 

where -n is the name of the image as it will appear in Glance, -a is the
availability zone, -u is the url of the image, -c is the url of the checksum
file, -t is the checksum digest, -r is the minimum amount of ram required by the
image, -d is the minimum amount of disk space required by the image and -f is
the disk format.

If successful, imagebuilder will return the id of the newly created image. You
can use this output in a build command, for example: 

`imagebuilder bootstrap <...> | xargs -I % imagebuilder build -s % <...>`

### Configuration
imagebuilder needs to know where to look for a Packer template and where to
store downloaded files (if using the -d option with the build command). You may
either store these paths in a config file, which should be located in
current/working directory, $HOME/.imagebuilder/config or
/etc/imagebuilder/config, or in environmental variables IB_TEMPLATE_DIR and
IB_DOWNLOAD_DIR.

Your config file could like this:

```
[main]
template_dir = /home/user/.imagebuilder
download_dir = /tmp/images
```

### Provision scripts
A provision script is (when using imagebuilder) simply a shell script that will
be executed on the virtual machine Packer builds an image from. In it's simplest
form it could be a list of commands but anything a shell can interpret will
work. Note that if your script has bash-specific commands in it, then put #!/bin/bash 
at the top of your script.

It's recommended that you test run your provision script in a virtual machine
before using it with imagebuilder (or Packer) as the output from the provision
script at runtime is rather limited.

See [this document](https://www.packer.io/docs/provisioners/shell.html) for more
information about provision scripts.

### Combining Openstack CLI with imagebuilder

#### Obtaining a source image ID

In order to build from a source image you'll need to obtain the image ID. You'll
find it in the Horizon GUI by clicking Images -> Public -> <image_name> and
copy-pasting "ID", but there is a more convenient way if you have the [Openstack
CLI tool
installed](http://docs.uh-iaas.no/en/latest/api.html#openstack-command-line-interface-cli):

`openstack image list --public`

will give you a table of available public images with their respective ID. In
combination with a command-line JSON-parser like
[jq](https://stedolan.github.io/jq) you could get the ID of an image name like
this

`openstack image list --public -f json | jq '.[] | select(.Name=="GOLD CentOS 7") | .ID'`

which could be useful in automated builds.

#### Listing availability zones

When using Packer with NREC setting the availability zone is also required.
`openstack availability zone list` lists availability zones for your region.
