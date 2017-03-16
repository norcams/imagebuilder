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
