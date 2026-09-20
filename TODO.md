* Exception handling
  * Isn't very good at the moment
  * Handle SIGTERM (clean up before dying). Exceptions and Ctrl-C already
    unwind through the try/finally in main(), but a SIGTERM kills the process
    without running it, so those builds still leak a security group and
    keypair. sweep_orphans() clears them up on a later run, but only once they
    are a day old

* Post-process images
  * Convert image from raw to qcow2 after download 
  `qemu-img convert -O qcow2 img.raw img.qcow2`
  * Compress image after download 
  `qemu-img convert -c -f qcow2 -O qcow2 -o cluster_size=2M img.qcow2 img_compressed.qcow2`
  * Upload after post-processing (for end-users)?

* Logging
  * Log to file

* Provisioners
  * Add support for Ansible as provisioner type

* More commands
  * Download
    * Post-processing options

* Autocomplete
  * Autocomplete with queries from Openstack
