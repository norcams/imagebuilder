import os
import configparser

class Config(object):
    def __init__(self, configfile_path=None):
        if configfile_path is None:
            self.configfile_path = [os.curdir,
                                    os.path.join(os.path.expanduser("~"), '.imagebuilder'),
                                    '/etc/imagebuilder']
        else:
            self.configfile_path = [configfile_path]
        self.config_file_list = []
        for path in self.configfile_path:
            self.config_file_list.append(os.path.join(path, "config"))
        self.config = self.__read_config()

    def show_config(self):
        # Not implemented yet
        pass

    def __read_config(self):
        config = configparser.ConfigParser()
        config.read(self.config_file_list)
        return config
