import re
from singleton import Singleton
from configparser import ConfigParser, NoOptionError


class Config(object):

    def __init__(self, file):
        self._load_config(file)
        # 用来判断是否为float类型
        self.is_float = re.compile(r'^[-+]?[0-9]+\.[0-9]+$')

    def __getattr__(self, name, section=None):
        if section is None:
            section = "DEFAULT"
        try:
            value = self.config.get(section, name)
            # ConfigParser get获得的结果为str类型
            if self.is_float.match(value):
                value = float(value)
            elif value.isdecimal():
                value = int(value)
            elif value in ['True', 'true']:
                value = True
            elif value in ['False', 'false']:
                value = False
        except NoOptionError:
            value = None

        return value

    def _load_config(self, config_file):
        self.config = ConfigParser()
        self.config.read(config_file)

    def get(self, name, section=None):
        return self.__getattr__(name, section)


@Singleton
class HciConfig(object):
    def __init__(self):
        self.base_config = Config("/usr/lib/python3.6/site-packages/pos-exporter/config/base.conf")

    def is_hci(self):
        return self.base_config.get("hci_enable", "hci")

    def get_zks_port(self):
        return str(self.base_config.get("port", "zookeeper"))
