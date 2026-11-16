import logging
import os
import urllib.request

from openstack.connection import Connection

from . import helpers

log = logging.getLogger(__name__)

# Blocking socket operations give up after this long. This is a per-read
# timeout, not a limit on the whole transfer, so a large image is fine as long
# as bytes keep arriving
SOCKET_TIMEOUT = 60

# Anything smaller than this is an error page, not a cloud image
MIN_IMAGE_BYTES = 1000

class BootstrapFunctions:
    def __init__(self,
                 session,
                 region):
        self.session = session
        self.tmp_dir = helpers.make_tmp_dir()
        self.conn = Connection(session=session, region_name=region)

    @staticmethod
    def find_expected_checksum(checksum_text, file_name):
        """Finds the checksum recorded for file_name in a checksum file

        Handles the two layouts in common use: the coreutils one, '<hash>
        <name>', where the name may carry a '*' prefix, and the BSD one,
        'SHA256 (<name>) = <hash>'. Returns the hash lowercased, or None when
        the file has no entry for this name.
        """
        for line in checksum_text.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '(' in line and ')' in line and '=' in line:
                name = line[line.index('(') + 1:line.rindex(')')]
                value = line.rsplit('=', 1)[1]
            else:
                fields = line.split()
                if len(fields) < 2:
                    continue
                value, name = fields[0], fields[-1].lstrip('*')
            if os.path.basename(name) == file_name:
                return value.strip().lower()
        return None

    def download_and_check(self, url, checksum_url=None, checksum_dig='sha256'):
        user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
        CHUNK      = 16 * 1024
        file_name  = url.split("/")[-1]
        file_path  = os.path.join(self.tmp_dir, file_name)

        # Checked up front so a typo in -t fails now rather than after the
        # download has finished
        if checksum_url and not helpers.valid_digest(checksum_dig):
            log.error("Unknown checksum digest: %s", checksum_dig)
            return None

        req = urllib.request.Request(
            url,
            data=None,
            headers = {
                'User-Agent':  user_agent
            }
        )
        response = urllib.request.urlopen(req, timeout=SOCKET_TIMEOUT)
        with open(file_path, "wb") as f:
            while True:
                chunk = response.read(CHUNK)
                if not chunk:
                    break
                f.write(chunk)
        response.close()

        # The size of what actually landed, not what the server claimed in a
        # header it is not obliged to send
        size = os.path.getsize(file_path)
        if size < MIN_IMAGE_BYTES:
            log.error("File is too small (%d bytes): %s", size, url)
            os.remove(file_path)
            return None

        if not checksum_url:
            return file_path

        req = urllib.request.Request(
            checksum_url,
            data=None,
            headers = {
                'User-Agent':  user_agent
            }
        )
        log.info("Verifying checksum of %s...", file_path)
        response = urllib.request.urlopen(req, timeout=SOCKET_TIMEOUT)
        checksum_text = response.read().decode('utf-8', errors='replace')
        response.close()
        log.debug(checksum_text)
        log.debug("Checksum type is %s", checksum_dig)

        actual = helpers.checksum_file(file_path, checksum_dig)
        expected = self.find_expected_checksum(checksum_text, file_name)

        if expected is None:
            # No entry naming this file. Fall back to the old behaviour of
            # looking for the hash anywhere in the file, which is weaker but
            # keeps working with checksum files that name things differently
            log.warning("No entry for %s in %s, falling back to matching the "
                        "hash anywhere in the file", file_name, checksum_url)
            if actual in checksum_text.lower():
                log.info("Checksum ok: %s", actual)
                return file_path
            log.error("Checksum not found: %s", actual)
            return None

        if actual == expected:
            log.info("Checksum ok: %s", actual)
            return file_path

        log.error("Checksum mismatch for %s: expected %s, got %s",
                  file_name, expected, actual)
        return None

    def create_glance_image(self, image_file, name, disk_format, min_disk,
                            min_ram, properties):
        try:
            # allow_duplicates keeps this a create: left at its default,
            # create_image returns an existing same-named image instead, and
            # this command's whole contract is to report a new image id.
            # disable_vendor_agent would otherwise add properties of its own
            image = self.conn.image.create_image(name=name,
                                                filename=image_file,
                                                disk_format=disk_format,
                                                container_format="bare",
                                                visibility="private",
                                                min_disk=min_disk,
                                                min_ram=min_ram,
                                                allow_duplicates=True,
                                                disable_vendor_agent=False,
                                                **properties)
        except Exception as error:
            log.error("Failed to upload %s: %s", image_file, error)
            return None
        log.info("Successfully uploaded %s as image %s", image_file, name)
        log.debug(image)
        return image.id
