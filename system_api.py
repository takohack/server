# _*_ coding:utf-8 _*_
# refactor on:2020/9/21 15:11
# Author   :youweisheng

import logger
import re
import configparser
import config
import psutil
import subprocess
import zk_client
import config_file
from emei.utils.config_center_util import ConfigCenterUtil
from mcast import Mcast


class SystemApi(object):
    EXPORTER_PORT = 9013

    def __init__(self, timeout):

        self.log = logger.Logger()

        self.hcicfg = config.HciConfig()
        self._data_sync = Mcast()
        if not self.hcicfg.is_hci():
            self.pos_target = "/component/public/rccpshennong/targets/pos.json"
            self.network_device = "/host/network_device"
            self.base_cfg_file = '/etc/rcos_private/pos/pdeployer_base.cfg'
            self.baseconfig = configparser.RawConfigParser()
            self.baseconfig.optionxform = lambda option: option
            self.baseconfig.read(self.base_cfg_file)
            self.dynamic_cfg_file = '/etc/rcos_private/pos/pdeployer_dynamic.cfg'
            self.dynamicconfig = configparser.RawConfigParser()
            self.dynamicconfig.optionxform = lambda option: option
            self.dynamicconfig.read(self.dynamic_cfg_file)
        self.localcfg = config_file.LocalNodeCfg()
        self.cfg = zk_client.ConfigCenter()
        self.timeout = int(timeout)
        self.mng_netcard = "rcosmgmt"

    # 执行命令并返回标准输出
    def process_stdout(self, command):
        try:
            # self.log.info("systemd_service popen command=" + repr(command))
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            output, errs = process.communicate(timeout=self.timeout)
            # self.log.info("systemd_service popen returncode=%d", process.returncode)
            return output, errs
        except Exception as e:
            self.log.info("%s exception: %s", command, repr(e))
            return b'', b''

    # 启动服务/进程
    def start_service(self, service):
        command = '/bin/systemctl start %s.service' % service
        self.process_stdout(command)

    # 关闭服务/进程
    def stop_service(self, service):
        # 调用subprocess.Popen关闭服务或者进程
        command = '/bin/systemctl stop %s.service' % service
        self.process_stdout(command)

    # 重启服务/进程
    def restart_service(self, service):
        self.stop_service(service)
        self.start_service(service)

    # 查看服务状态
    def service_status(self, service):
        command = '/bin/systemctl status %s.service' % service
        command_output, command_errors = self.process_stdout(command)
        stdout_list = command_output.decode('utf-8')
        if '(running)' in stdout_list:
            return True
        else:
            return False

    # 判断当前节点是否是主节点
    def is_master_node(self):
        master_id = self.cfg.get_pos_masterid()
        my_id = self.cfg.read_myid()
        if master_id == my_id:
            return True
        else:
            return False

    def is_ip(self, ip_addr):
        check_ip = re.compile(
            r'^(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|[1-9])\.(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|\d)\.(1\d{2}|2[0-4]\d|25'
            r'[0-5]|[1-9]\d|\d)\.(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|\d)$')
        if check_ip.match(ip_addr):
            return True
        else:
            return False

    # 取当前节点的管理网IP
    def get_local_manage_ip(self):
        info = psutil.net_if_addrs()
        for name, v in info.items():
            if name != self.mng_netcard:
                continue
            for item in v:
                if self.is_ip(item[1]):
                    return item[1]
        return None

    # 获取特定节点的管理网IP
    def get_manage_ip(self, uuid):
        network_device_list = ConfigCenterUtil.get_config(self.network_device)
        for network_device in network_device_list:
            if 'network_list' not in network_device or 'node_id' not in network_device:
                continue
            if str(network_device['node_id']) != uuid:
                continue
            for network in network_device['network_list']:
                if 'device_name' not in network or 'ipv4' not in network or 'ip_addr' not in network['ipv4']:
                    continue
                if network['device_name'] != 'bond0':
                    continue
                ip_addr = network['ipv4']['ip_addr']
                if self.is_ip(ip_addr):
                    return ip_addr
        return None

    def get_all_snet_ip(self):
        ip_list = []
        network_device_list = ConfigCenterUtil.get_config(self.network_device)
        for network_device in network_device_list:
            if 'network_list' not in network_device:
                continue
            for network in network_device['network_list']:
                if 'device_name' not in network or 'ipv4' not in network or 'ip_addr' not in network['ipv4']:
                    continue
                if network['device_name'] != 'bond2':
                    continue
                ip_addr = network['ipv4']['ip_addr']
                if self.is_ip(ip_addr):
                    ip_list.append(ip_addr)
        self.log.info("ip_list = %s", ip_list)
        return ip_list

    # 判断当前集群中是否还有可用节点
    def is_cluster_null(self):
        node_config_fpath = ConfigCenterUtil.get_config_prefix(
            "/component/private/rcos-pos/cluster/node", is_full_path=True)
        for node_config_path in node_config_fpath.keys():
            node_config = ConfigCenterUtil.get_config(node_config_path)
            if node_config == 1:
                # 如果有节点部署，才往下执行
                return False
        return True

    # 判断pos的监控采集点配置是否存在
    def is_exist_pos_target(self):
        try:
            config = ConfigCenterUtil.get_config(self.pos_target)
            if config is None:
                return False
            else:
                return True
        except Exception:
            return False

    # 读取pos的监控采集点配置
    def read_pos_target(self):
        try:
            jsoncfg = ConfigCenterUtil.get_config(self.pos_target)
            return jsoncfg
        except Exception as e:
            self.log.warning("read prometheus pos target failed: %s", repr(e))
            return None

    # 保存pos的监控采集点配置
    def write_pos_target(self, jsoncfg):
        try:
            ConfigCenterUtil.set_config(self.pos_target, jsoncfg)
        except Exception as e:
            self.log.warning("write prometheus pos target failed: %s", repr(e))

    # 更新pos的监控采集点配置
    def update_pos_target(self, svip):
        try:
            new_addr_list = []
            new_addr_list.append(str(svip) + ":" + str(self.EXPORTER_PORT))
            if not self.is_exist_pos_target():
                self.log.info("create pos target: %s", repr(new_addr_list))
                jsoncfg = [{"labels": {}, "targets": []}]
                for alarm_addr in new_addr_list:
                    jsoncfg[0]['targets'].append(str(alarm_addr))
                self.write_pos_target(jsoncfg)
            else:
                jsoncfg = ConfigCenterUtil.get_config(self.pos_target)
                old_addr_list = jsoncfg[0]['targets']
                new_addr_list.sort()
                old_addr_list.sort()
                if new_addr_list != old_addr_list:
                    self.log.info("update pos target: %s", repr(new_addr_list))
                    jsoncfg = [{"labels": {}, "targets": []}]
                    for alarm_addr in new_addr_list:
                        jsoncfg[0]['targets'].append(str(alarm_addr))
                    self.write_pos_target(jsoncfg)
        except Exception as e:
            self.log.warning("update pos target except:%s", repr(e))
            jsoncfg = [{"labels": {}, "targets": []}]
            for alarm_addr in new_addr_list:
                jsoncfg[0]['targets'].append(str(alarm_addr))
            self.write_pos_target(jsoncfg)

    # 启动udp数据同步服务
    def is_mcast_server_running(self):
        return self._data_sync.is_running()

    # 启动udp数据同步服务
    def start_mcast_server(self, get_ip_list):
        self._data_sync.start_server(get_ip_list)

    # 停止UDP数据同步服务
    def stop_mcast_server(self):
        self._data_sync.stop_server()

    # 报文的发送
    def send_mcast_msg(self, chnn, key, msg: str, ip=None):
        return self._data_sync.send_msg(chnn, key=key, msg=msg, ip=ip)

    # 注册主播监听
    def register_mcast_listener(self, chnn, callback):
        self._data_sync.register_listener(chnn=chnn, callback=callback)
        return True
