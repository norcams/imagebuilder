# imagebuilder

Image Builder for UH IaaS

imagebuilder is a Command Line Interface for building fully provisioned,
ready-to-use images/snapshots in UH IaaS using [Packer](https://packer.io).

It's basically just a wrapper for Packer doing the necessary steps required to
make Packer work with UH IaaS default configurations, and without the need to
make or edit templates.

imagebuilder is meant to simplify the process of making and automate the
buildling of machine images in UH IaaS using only the command-line. For more
advanced image building you should learn [how to use
Packer](https://www.packer.io/docs/).

**Please note that this tool is under development. Feel free to try but don't
expect it to work properly. It may very well mess up your project at this stage
so use with caution!**

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

When using Packer with UH-IaaS setting the availability zone is also required.
`openstack availability zone list` lists availability zones for your region.
