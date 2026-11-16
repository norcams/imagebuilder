packer {
  required_plugins {
    openstack = {
      version = "~> 1.1"
      source  = "github.com/hashicorp/openstack"
    }
  }
}

variable "image_name" {
  type = string
}

variable "source_image" {
  type = string
}

variable "flavor" {
  type = string
}

variable "network" {
  type = string
}

variable "security_group" {
  type = string
}

variable "ssh_username" {
  type = string
}

variable "ssh_keypair_name" {
  type = string
}

variable "ssh_key_path" {
  type = string
}

variable "availability_zone" {
  type = string
}

variable "manifest_path" {
  type = string
}

variable "provision_script" {
  type    = string
  default = "/bin/true"
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
  ssh_ip_version       = "4"
  ssh_pty              = true
  availability_zone    = var.availability_zone
}

build {
  sources = ["source.openstack.image"]

  provisioner "shell" {
    scripts = [
      "${path.root}/../scripts/upgrade.sh",
      var.provision_script,
      "${path.root}/../scripts/cleanup.sh",
    ]
  }

  post-processor "manifest" {
    output = var.manifest_path
  }
}
