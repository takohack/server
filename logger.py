# _*_ coding:utf-8 _*_
# refactor on:2020/9/21 15:11
# Author   :youweisheng

import os
import sys
import logging
import logging.handlers
from singleton import Singleton


@Singleton
class Logger(object):
    def __init__(self, name=os.path.split(os.path.splitext(sys.argv[0])[0])[-1],
                 log_name="pos-exporter.log"):
        self.max_bytes = 0  # 默认50MB
        self.backup_count = 0
        self.set_level = "INFO"
        self.log_path = "/var/log/rcos/pos-exporter"
        self.format = "%(asctime)s %(levelname)s [%(process)d:%(thread)d] [%(pathname)s:%(lineno)s] <%(" \
                      "funcName)s> %(message)s "
        self.use_console = False
        self.__logger = logging.getLogger(name)
        self.setLevel(getattr(logging, self.set_level.upper()) if hasattr(logging, self.set_level.upper()) else logging.INFO)  # 设置日志级别
        if not os.path.exists(self.log_path):  # 创建日志目录
            os.makedirs(self.log_path)
        formatter = logging.Formatter(self.format)
        handler_list = list()
        handler_list.append(logging.handlers.RotatingFileHandler(os.path.join(self.log_path, log_name),
                                                                 maxBytes=self.max_bytes, backupCount=self.backup_count,
                                                                 encoding='utf-8'))
        if self.use_console:
            handler_list.append(logging.StreamHandler())
        for handler in handler_list:
            handler.setFormatter(formatter)
            self.addHandler(handler)

    def __getattr__(self, item):
        return getattr(self.logger, item)

    @property
    def logger(self):
        return self.__logger

    @logger.setter
    def logger(self, func):
        self.__logger = func

    @staticmethod
    def _exec_type():
        return "DEBUG" if os.environ.get("IPYTHONENABLE") else "INFO"
