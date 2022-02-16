# _*_ coding:utf-8 _*_
# refactor on:2020/11/25 10:17
# Author   :youweisheng

from emei.base.singleton import SingletonBase
from emei.framework.server.api import RestApi
from emei.framework.server.rccpserver import RCCPServer
from emei.framework.server.api import RestEndpoint
from prometheus_client import generate_latest
import logger


class MetricsController(RestEndpoint):
    @staticmethod
    def get(**kwargs):
        return generate_latest()


class RestfulAPI(metaclass=SingletonBase):
    def __init__(self):
        self.restful_api = RestApi(name="pos-exporter")

    def set_api(self):
        self.restful_api.add_endpoint("/metrics", MetricsController)

    def get_api(self):
        return self.restful_api


class ServerManager(metaclass=SingletonBase):
    def __init__(self):
        self.log = logger.Logger()
        PRI_CONFIG = "/usr/lib/python3.6/site-packages/pos-exporter/config/pos-exporter-pri.conf"
        PUB_CONFIG = "/etc/rcos_global/component_pub_cnf.d/pos-exporter.conf"
        self.rccpserver = RCCPServer([PRI_CONFIG], [PUB_CONFIG])
        RestfulAPI().set_api()
        self.rccpserver.add_api("pos-exporter", RestfulAPI().get_api())

    def start(self):
        self.log.info("ServerManager start")
        self.rccpserver.start()
