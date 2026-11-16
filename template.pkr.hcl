packer {
  required_plugins {
    openstack = {
      version = "~> 1.1"
      source  = "github.com/hashicorp/openstack"
    }
  }
}

variable "image_name" {
  type        = string
  description = "Name of the resulting image in Glance"
}

variable "source_image" {
  type        = string
  description = "ID of the image to build from"
}

variable "flavor" {
  type        = string
  description = "Flavor of the build instance"
}

variable "network" {
  type        = string
  description = "ID of the network to attach the build instance to"
}

variable "security_group" {
  type        = string
  description = "Name of the temporary security group"
}

variable "ssh_username" {
  type        = string
  description = "User created by cloud-init in the source image"
}

variable "ssh_keypair_name" {
  type        = string
  description = "Name of the temporary keypair as stored in OpenStack"
}

variable "ssh_key_path" {
  type        = string
  description = "Path to the private key matching ssh_keypair_name"
}

variable "availability_zone" {
  type        = string
  description = "Availability zone to build in"
}

variable "manifest_path" {
  type        = string
  description = "Where the manifest post-processor writes the build result"
}

variable "provision_script" {
  type        = string
  description = "User supplied provision script"
  default     = "/bin/true"
}

source "openstack" "image" {
  image_name           = var.image_name
  source_image         = var.source_image
  flavor               = var.flavor
  networks             = [var.network]
  security_groups      = [var.security_group]
  ssh_username         = var.ssh_username
  ssh_keypair_name     = var.ssh_keypair_name
  ssh_private_key_file = var.ssh_key_path
  ssh_pty              = true
  availability_zone    = var.availability_zone
}

build {
  sources = ["source.openstack.image"]

  provisioner "shell" {
    scripts = [
      "${path.root}/scripts/uio-rhel.sh",
      "${path.root}/scripts/fstrim.sh",
      "${path.root}/scripts/qemu_guest_agent.sh",
      "${path.root}/scripts/upgrade.sh",
      "${path.root}/scripts/enable_ipv6.sh",
      "${path.root}/scripts/autopatch.sh",
      "${path.root}/scripts/report.sh",
      "${path.root}/scripts/sshd_hardening.sh",
      var.provision_script,
      "${path.root}/scripts/cleanup.sh",
      "${path.root}/scripts/uio-cleanup.sh",
    ]
  }

  post-processor "manifest" {
    output = var.manifest_path
  }
}
