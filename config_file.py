# _*_ coding:utf-8 _*_
# refactor on:2021/3/9 17:29
# Author   :youweisheng
import configparser
import json
import threading
import logger
import os
import config
from singleton import Singleton


@Singleton
class LogPositionCfg(object):
    def __init__(self):
        self.log = logger.Logger()
        self.hcicfg = config.HciConfig()
        if self.hcicfg.is_hci():
            self.cfg_path = "/usr/lib/python3.6/site-packages/pos-exporter/config/log_position.cfg"
        else:
            self.cfg_path = "/etc/rcos_private/pos/log_position.cfg"
        self.cfg_parser = configparser.RawConfigParser()
        self.cfg_parser.optionxform = lambda option: option

    def get_log_position(self, log_path):
        self.cfg_parser.read(self.cfg_path)
        if self.cfg_parser.has_option(log_path, 'lastline'):
            return self.cfg_parser.get(log_path, 'lastline')
        else:
            return None

    def set_log_poistion(self, log_path, logmsg):
        if not self.cfg_parser.has_section(log_path):
            self.cfg_parser.add_section(log_path)
        self.cfg_parser[log_path]['lastline'] = logmsg
        with open(self.cfg_path, 'w') as configfile:
            self.cfg_parser.write(configfile, space_around_delimiters=False)


@Singleton
class AlertTemp(object):
    def __init__(self):
        self.num_lock = threading.Lock()
        self.log = logger.Logger()
        self.cfg_path = "/var/log/rcos/pos-exporter/alertbuffer/"
        if not os.path.exists(self.cfg_path):
            os.makedirs(self.cfg_path)

    def get_file_count(self):
        list_file = os.listdir(self.cfg_path)
        return len(list_file)

    def get_new_filenum(self):
        list_file = os.listdir(self.cfg_path)
        if len(list_file) > 0:
            return int(max(list(map(int, list_file)))) + 1
        else:
            return 0

    # -1表示没有需要处理的告警
    def get_min_filenum(self):
        list_file = os.listdir(self.cfg_path)
        if list_file is not None and len(list_file) > 0:
            return int(min(list(map(int, list_file))))
        else:
            return -1

    def get_filemsg(self, num):
        filepath = self.cfg_path + str(num)
        try:
            with open(filepath, 'r') as file:
                return json.loads(file.read())
        except Exception as e:
            self.log.error("alert buffer msg is %s", repr(e))
            return None

    def del_filenum(self, num):
        filepath = self.cfg_path + str(num)
        if os.path.exists(filepath):  # 如果文件存在
            os.remove(filepath)

    def insert_alert_tmp(self, msg):
        # 这个要加锁
        try:
            self.num_lock.acquire()
            num = self.get_new_filenum()
            filepath = self.cfg_path + str(num)
            self.log.info("save alert event in %s, msg:%s", filepath, msg)
            with open(filepath, 'w') as file:
                file.write(json.dumps(msg))
        except Exception as e:
            self.log.error("insert alarm except: %s", repr(e))
        finally:
            if self.num_lock.locked():
                self.num_lock.release()

    def get_alert_tmp(self):
        try:
            self.num_lock.acquire()
            msg = None
            if self.get_file_count() > 0:
                num = self.get_min_filenum()
                if num >= 0:
                    msg = self.get_filemsg(num)
        except Exception as e:
            self.log.error("get alert except: %s", repr(e))
        finally:
            if self.num_lock.locked():
                self.num_lock.release()
            return msg

    def del_alert_tmp(self):
        try:
            self.num_lock.acquire()
            if self.get_file_count() > 0:
                num = self.get_min_filenum()
                if num >= 0:
                    self.del_filenum(num)
        except Exception as e:
            self.log.error("del alert except: %s", repr(e))
        finally:
            if self.num_lock.locked():
                self.num_lock.release()


@Singleton
class LocalNodeCfg(object):
    def __init__(self):
        self.log = logger.Logger()
        self.hcicfg = config.HciConfig()
        if not self.hcicfg.is_hci():
            self.base_cfg_file = '/etc/rcos_private/pos/pdeployer_base.cfg'
            self.baseconfig = configparser.RawConfigParser()
            self.baseconfig.optionxform = lambda option: option
            self.baseconfig.read(self.base_cfg_file)
            self.dynamic_cfg_file = '/etc/rcos_private/pos/pdeployer_dynamic.cfg'
            self.dynamicconfig = configparser.RawConfigParser()
            self.dynamicconfig.optionxform = lambda option: option
            self.dynamicconfig.read(self.dynamic_cfg_file)

    # 读取myid文件
    def read_myid(self):
        self.baseconfig.read(self.base_cfg_file)
        myidfile = self.baseconfig.get('zookeeper_conf', 'myid')
        with open(myidfile) as f:
            zkmyid = f.read().rstrip('\n')  # 打开文件去除换行符
        return zkmyid

    def is_config(self):
        if self.hcicfg.is_hci():
            # 如果未部署，是不会启动该容器的，所以如果程序有运行，肯定是部署了
            return 1
        else:
            self.dynamicconfig.read(self.dynamic_cfg_file)
            return int(self.dynamicconfig.get('p-deployer_config', 'is_config'))

    # 获取当前节点类型
    def is_arbitrate_node(self):
        if self.hcicfg.is_hci():
            # HCI无仲裁节点
            return False
        else:
            self.dynamicconfig.read(self.dynamic_cfg_file)
            if self.dynamicconfig.has_option('p-deployer_config', 'arbitrate'):
                arbitrate = self.dynamicconfig.get('p-deployer_config', 'arbitrate')
                if int(arbitrate) == 1:
                    return True
            return False

    def get_client_port(self):
        if self.hcicfg.is_hci():
            return self.hcicfg.get_zks_port()
        else:
            self.baseconfig.read(self.base_cfg_file)
            return self.baseconfig.get('zookeeper', 'clientPort')
