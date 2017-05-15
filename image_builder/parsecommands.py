import argparse
import sys

class Commands(object):

    def __init__(self):
        parser = argparse.ArgumentParser(
            description='Usage',
            usage='''imagebuilder <command> [<args>]

   build          Builds an image
   bootstrap      Downloads a cloud-ready image from a URL and uploads to Glance
''')
        parser.add_argument('command', help='Subcommand to run')
        args = parser.parse_args(sys.argv[1:2])
        if not hasattr(self, args.command):
            print('Unrecognized command')
            parser.print_help()
            exit(1)
        self.build_args = False
        self.bootstrap_args = False
        getattr(self, args.command)()

    def build(self):
        parser = argparse.ArgumentParser(description='Build an image')
        parser.add_argument('-a', '--availability-zone',
                            help='Availability zone, i.e. bgo-default-1, osl-default-1',
                            default=False,
                            required=True)
        parser.add_argument('-d', '--download',
                            help='Download image after build',
                            action='store_true',
                            default=False)
        parser.add_argument('-n', '--name',
                            help='Name of the image',
                            default=False,
                            required=True)
        parser.add_argument('-p', '--provision-script',
                            help='Path to your provision script',
                            default='/bin/true')
        parser.add_argument('-s', '--source-image',
                            help='Name or id of the source image we build from',
                            default=False,
                            required=True)
        parser.add_argument('-u', '--ssh-username',
                            help='SSH username as set up by cloud-init (usually named after distro or OS, i.e. centos, ubuntu)',
                            default=False,
                            required=True),
        parser.add_argument('-v', '--verbose',
                            help='Be verbose (default is no output)',
                            action='store_true',
                            default=False)
        parser.add_argument('--debug',
                            help='Debug mode',
                            action='store_true',
                            default=False)
        self.build_args = parser.parse_args(sys.argv[2:])
        return self.build_args

    def bootstrap(self):
        parser = argparse.ArgumentParser(
            description='Downloads a cloud-ready image from a URL and uploads to glance')
        parser.add_argument('-a', '--availability-zone',
                            help='Availability zone, i.e. bgo-default-1, osl-default-1',
                            default=False,
                            required=True)
        parser.add_argument('-u', '--url',
                            help='URL to upstream image',
                            default=False,
                            required=True)
        parser.add_argument('-c', '--checksum-url',
                            help='URL to checksum file',
                            default=None,
                            required=False)
        parser.add_argument('-t', '--checksum-digest',
                            help='Checksum digest (defaults to sha256)',
                            default='sha256',
                            required=False),
        parser.add_argument('-n', '--name',
                            help='Name of the image',
                            default=False,
                            required=True),
        parser.add_argument('-r', '--min-ram',
                            help='Minimum amount of ram in MB',
                            default=False,
                            required=True)
        parser.add_argument('-d', '--min-disk',
                            help='Minimum amount of disk in GB',
                            default=False,
                            required=True)
        parser.add_argument('-f', '--disk-format',
                            help='Format of the disk',
                            default=False,
                            required=True)
        parser.add_argument('-v', '--verbose',
                            help='Be verbose',
                            action='store_true',
                            default=False)
        parser.add_argument('--debug',
                            help='Debug mode',
                            action='store_true',
                            default=False)
        self.bootstrap_args = parser.parse_args(sys.argv[2:])
        return self.bootstrap_args
