import logging
import os
import urllib.request
from glanceclient import Client
from .helpers import Helpers as helpers

class BootstrapFunctions(object):
    def __init__(self,
                 session,
                 region,
                 avail_zone):
        self.session = session
        self.avail_zone = avail_zone
        self.tmp_dir = helpers.make_tmp_dir()
        self.glance = Client("2", session=session, region_name=region)

    def download_and_check(self, url, checksum_url=None, checksum_dig='sha256'):
        user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
        CHUNK      = 16 * 1024
        file_name  = url.split("/")[-1]
        file_path  = os.path.join(self.tmp_dir, file_name)
        req = urllib.request.Request(
            url,
            data=None,
            headers = {
                'User-Agent':  user_agent
            }
        )
        response = urllib.request.urlopen(req)
        with open(file_path, "wb") as f:
            while True:
                chunk = response.read(CHUNK)
                if not chunk:
                    break
                f.write(chunk)
        response.close()
        if int(response.headers["content-length"]) < 1000:
            logging.info("File is too small: %s" % url)
            os.remove(file_path)
            return None
        if checksum_url:
            req = urllib.request.Request(
                checksum_url,
                data=None,
                headers = {
                    'User-Agent':  user_agent
                }
            )
            logging.info("Verifying checksum of %s..." % file_path)
            response = urllib.request.urlopen(req)
            checksum_all = str(response.read())
            response.close()
            logging.debug(checksum_all)
            logging.debug("Checksum type is %s" % checksum_dig)
            checksum_file = helpers.checksum_file(file_path, checksum_dig)
            if checksum_file in checksum_all:
                logging.info("Checksum ok: %s" % checksum_file)
                return file_path
            else:
                logging.info("Checksum not ok: %s" % checksum_file)
                return None
        else:
            return file_path

    def create_glance_image(self, image_file, name, disk_format, min_disk,
                            min_ram, properties):
        image = self.glance.images.create(name=name,
                                          visibility="private",
                                          disk_format=disk_format,
                                          min_disk=min_disk,
                                          min_ram=min_ram,
                                          container_format="bare",
                                          **properties)
        logging.info("Created image %s" % name)
        logging.debug(image)
        try:
            self.glance.images.upload(image.id, open(image_file, "rb"))
            logging.info("Successfully uploaded %s" % image_file)
            return image.id
        except BaseException as error:
            logging.debug(error)
            return None
