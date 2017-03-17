import functools
import hashlib
import logging
import shutil
import tempfile

class Helpers(object):

    @staticmethod
    def clean_tmp_files(tmp_dir):
        logging.info('Removing temporary directory with content...')
        shutil.rmtree(tmp_dir)

    @staticmethod
    def make_tmp_dir():
        logging.info('Creating a directory for temporary files...')
        tmp_dir = tempfile.mkdtemp(prefix='imagebuilder-')
        return tmp_dir

    @staticmethod
    def log_subprocess_output(pipe):
        for line in iter(pipe.readline, b''):
            logging.info('%r', line)

    @staticmethod
    def checksum_file(file_path, chunk_size=65536):
        """Read the file in small pieces, so as to prevent failures to read
        particularly large files.  Also ensures memory usage is kept to a
        minimum. Testing shows default is a pretty good size."""
        assert isinstance(chunk_size, int) and chunk_size > 0
        sha256 = hashlib.sha256()
        #pylint: disable=invalid-name
        with open(file_path, 'rb') as f:
            for block in iter(lambda: f.read(chunk_size), b''):
                sha256.update(block)
        checksum = sha256.hexdigest()
        logging.debug("hexdigest of %s is %s" % (file_path, checksum))
        return checksum
