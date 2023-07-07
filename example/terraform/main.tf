module "node" {
  source = "git::https://github.com/raykrist/tf-nrec-node.git"

  name              = "imagetest"
  node_name         = "imagetest"
  region            = "bgo"
  node_count        = 1
  ssh_public_key    = "~/.ssh/id_rsa.pub"
  allow_ssh_from_v6 = ["2001:700:200::/48"]
  allow_ssh_from_v4 = ["129.177.0.0/16"]
  network           = "dualStack"
  flavor            = "m1.large"
  image_id          = "<image id from build>"
  image_user        = "almalinux"
  volume_size       = 0
}
