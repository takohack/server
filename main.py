# _*_ coding:utf-8 _*_
# refactor on:2020/9/21 15:11
# Author   :youweisheng

import log_collect
import monitor
import master
import time
import os
import system_api
import logger
import zk_client
import config_file
import threading
import config
from restapi import ServerManager
from prometheus_client import start_http_server


class Connect_Control(object):
    def __init__(self):
        self.log = logger.Logger()
        self.cfg = zk_client.ConfigCenter()
        self.sys = system_api.SystemApi(5)
        self.connect_lost_flag = True
        self.alertpro = log_collect.AlertProcess()
        self.conn_delay_cycle_s = 1
        self.conn_retry_cycle_s = 10

    def connection_listener(self, state):
        try:
            self.log.info("exporter recv zks event, zkstate=%s", repr(state))
            self.cfg.set_state(state)
            # 如果发生断连再连上
            if state == "CONNECTED" and self.connect_lost_flag:
                self.connect_lost_flag = False
                threading.Thread(target=self.alertpro.start, args=()).start()
            elif state == "LOST" or state == "SUSPENDED":
                self.connect_lost_flag = True
                # 如果网络断连，并且当前集群中已经无可用节点，说明最后一个节点也被删除了，此时需要移除告警
                if self.sys.is_cluster_null():
                    threading.Thread(target=self.alertpro.remove_exporter_alarm, args=()).start()
        except Exception as e:
            self.log.error("connection listener process except: %s", repr(e))

    def start(self):
        last_conn_time = time.perf_counter()
        while True:
            try:
                localcfg = config_file.LocalNodeCfg()
                cfg = zk_client.ConfigCenter()
                if localcfg.is_config() == 1:
                    if not cfg.is_zks_connect():
                        if hcicfg.is_hci():
                            localhost_ip = os.getenv('localhost_ip')
                        else:
                            localhost_ip = "127.0.0.1"
                        zk_server = localhost_ip + ":" + localcfg.get_client_port()
                        while (time.perf_counter() - last_conn_time) <= self.conn_retry_cycle_s:
                            self.log.info("wait connect to zk (%s)s",
                                          str(self.conn_retry_cycle_s - (time.perf_counter() - last_conn_time)))
                            time.sleep(1)
                        self.log.info("connect to zk_sever=" + zk_server)
                        cfg.closetozkserver()
                        cfg.connettozkserver(zk_server, self.connection_listener)
                        last_conn_time = time.perf_counter()
                time.sleep(self.conn_delay_cycle_s)
            except Exception as e:
                self.log.error("create connect except : %s", repr(e))
                time.sleep(self.conn_delay_cycle_s)


def start_https_server():
    try:
        if hcicfg.is_hci():
            # python原生的prometheus支持HTTP的exporter server
            start_http_server(9013)
        else:
            # emei框架支持HTTPS的exporter server
            ServerManager().start()
    except Exception as e:
        log.error("start_http_server exception: %s", repr(e))
        raise Exception("start https except")


if __name__ == "__main__":
    connect_lost_flag = True
    exporter_exit_delay_s = 5
    log = logger.Logger()
    try:
        hcicfg = config.HciConfig()
        log.info("start alarm log collect")
        myalert = log_collect.AlarmModule()
        threading.Thread(target=myalert.start, args=()).start()
        log.info("start pos monitor")
        mymonitor = monitor.Monitor()
        threading.Thread(target=mymonitor.start, args=()).start()
        log.info("start master ctrl process")
        mymaster = master.Master()
        threading.Thread(target=mymaster.start, args=()).start()
        log.info("start create zk connect")
        connctl = Connect_Control()
        threading.Thread(target=connctl.start, args=()).start()
        log.info("start http server")
        start_https_server()
    except Exception as e:
        log.error("exporter Exception: %s", repr(e))
        time.sleep(exporter_exit_delay_s)
        os._exit(1)
