import argparse


class Commands:

    def __init__(self, argv=None):
        parser = argparse.ArgumentParser(
            prog='imagebuilder',
            description='Build fully provisioned images in NREC')
        # Subparsers rather than dispatching on getattr(self, argv[1]): that
        # made every attribute on this object reachable from the command line,
        # and left the list of commands as prose in the usage string with
        # nothing keeping it honest
        subcommands = parser.add_subparsers(dest='command', required=True,
                                            metavar='<command>')

        build = subcommands.add_parser(
            'build',
            help='Builds an image',
            description='Build an image')
        build.add_argument('-a', '--availability-zone',
                           help='Availability zone, i.e. bgo-default-1, osl-default-1',
                           required=True)
        build.add_argument('-d', '--download',
                           help='Download image after build',
                           action='store_true',
                           default=False)
        build.add_argument('-f', '--flavor',
                           help='Flavor to use when building (default: m1.small)',
                           default='m1.small')
        build.add_argument('-n', '--name',
                           help='Name of the image',
                           required=True)
        build.add_argument('-N', '--network-name',
                           help='Name of the network we want to use',
                           default='Dualstack')
        build.add_argument('-p', '--provision-script',
                           help='Path to your provision script',
                           default='/bin/true')
        build.add_argument('-s', '--source-image',
                           help='Name or id of the source image we build from',
                           required=True)
        build.add_argument('-u', '--ssh-username',
                           help='SSH username as set up by cloud-init (usually named after distro or OS, i.e. centos, ubuntu)',
                           required=True)
        build.add_argument('-v', '--verbose',
                           help='Be verbose (default is no output)',
                           action='store_true',
                           default=False)
        build.add_argument('--no-sweep',
                           help='Do not remove temporary security groups and '
                                'keypairs left behind by runs that were killed',
                           action='store_true',
                           default=False)
        build.add_argument('-x', '--purge-source',
                           help='Purge source image you are building from',
                           action='store_true',
                           default=False)
        build.add_argument('--debug',
                           help='Debug mode',
                           action='store_true',
                           default=False)

        bootstrap = subcommands.add_parser(
            'bootstrap',
            help='Downloads a cloud-ready image from a URL and uploads to Glance',
            description='Downloads a cloud-ready image from a URL and uploads to glance')
        bootstrap.add_argument('-a', '--availability-zone',
                               help='Availability zone, i.e. bgo-default-1, osl-default-1',
                               required=True)
        bootstrap.add_argument('-u', '--url',
                               help='URL to upstream image',
                               required=True)
        bootstrap.add_argument('-c', '--checksum-url',
                               help='URL to checksum file',
                               default=None)
        bootstrap.add_argument('-t', '--checksum-digest',
                               help='Checksum digest (defaults to sha256)',
                               default='sha256')
        bootstrap.add_argument('-n', '--name',
                               help='Name of the image',
                               required=True)
        bootstrap.add_argument('-r', '--min-ram',
                               help='Minimum amount of ram in MB',
                               type=int,
                               required=True)
        bootstrap.add_argument('-d', '--min-disk',
                               help='Minimum amount of disk in GB',
                               type=int,
                               required=True)
        bootstrap.add_argument('-f', '--disk-format',
                               help='Format of the disk',
                               required=True)
        bootstrap.add_argument('-s', '--no-scsi-mode',
                               help='Do not create image with scsi disk properties',
                               action='store_true',
                               default=False)
        bootstrap.add_argument('-e', '--efi',
                               help='Boot image with uefi boot firmware',
                               action='store_true',
                               default=False)
        bootstrap.add_argument('-v', '--verbose',
                               help='Be verbose',
                               action='store_true',
                               default=False)
        bootstrap.add_argument('--debug',
                               help='Debug mode',
                               action='store_true',
                               default=False)

        args = parser.parse_args(argv)
        self.command = args.command
        self.build_args = args if args.command == 'build' else None
        self.bootstrap_args = args if args.command == 'bootstrap' else None
