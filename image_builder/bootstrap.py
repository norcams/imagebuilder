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
        file_name = url.split("/")[-1]
        file_path = os.path.join(self.tmp_dir, file_name)
        (image_file, headers) = urllib.request.urlretrieve(url, file_path)
        if int(headers["content-length"]) < 1000:
            logging.info("File is too small: %s" % url)
            os.remove(file_name)
            return None
        if checksum_url:
            logging.info("Verifying checksum of %s..." % file_path)
            response = urllib.request.urlopen(checksum_url)
            checksum_all = str(response.read())
            response.close()
            logging.debug(checksum_all)
            logging.debug("Checksum type is %s" % checksum_dig)
            checksum_file = helpers.checksum_file(file_path, checksum_dig)
            if checksum_file in checksum_all:
                logging.info("Checksum ok: %s" % checksum_file)
                return image_file
            else:
                logging.info("Checksum not ok: %s" % checksum_file)
                return None
        else:
            return image_file

    def create_glance_image(self, image_file, name, disk_format, min_disk, min_ram):
        image = self.glance.images.create(name=name,
                                          visibility="private",
                                          disk_format=disk_format,
                                          min_disk=min_disk,
                                          min_ram=min_ram,
                                          container_format="bare")
        logging.info("Created image %s" % name)
        logging.debug(image)
        try:
            self.glance.images.upload(image.id, open(image_file, "rb"))
            logging.info("Successfully uploaded %s" % image_file)
            return image.id
        except BaseException as error:
            logging.debug(error)
            return None
