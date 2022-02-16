# _*_ coding:utf-8 _*_
# refactor on:2020/9/21 15:11
# Author   :youweisheng

import pos_rpc
from bp_rpc import RemoteBackupJSONRPCClient
from exporter import MetricNode
import time
import logger
import re
import system_api
import zk_client
import json
import config
from enum import Enum
import copy
import config_file
from sock_kv import SocketKVpair


class ParamType(Enum):
    TYPE_SCSI = 1
    TYPE_CACHE = 2
    TYPE_CAPACITY = 3
    TYPE_BACKUP = 4
    TYPE_ZK = 5
    TYPE_DISK = 6


class Monitor(object):
    def __init__(self):
        self.wait_conn_zks_time_s = 1
        self.monitor_cycle_s = 30
        self.log = logger.Logger()
        self.hcicfg = config.HciConfig()
        self.cfg = zk_client.ConfigCenter()
        self.kv_cfg = None
        self.is_pos_master = False
        self.monitor_list = None
        self.capacity_list = None
        self.monitor_param_init()
        self.sys = system_api.SystemApi(5)
        self.localcfg = config_file.LocalNodeCfg()

    def master_sync(self):
        master_id = self.cfg.get_pos_masterid()
        my_id = self.cfg.read_myid()
        if master_id == my_id:
            self.is_pos_master = True
        else:
            self.is_pos_master = False

    def save_param_to_kv(self):
        replace_list = ['DataL1Hits', 'DataL2Hits', 'DataMisses']
        # 这几个值是每次只取得到累加值，而不是总量
        add_list = ['ReadIO', 'WriteIO', 'ReadByte', 'WriteByte', 'ReadLatency', 'WriteLatency']

        # 保存集群监控信息
        if self.is_pos_master:
            self.kv_cfg.cfg_save_cluster_monitor(json.dumps(self.capacity_list))
        # 保存节点监控信息
        # 创建存放监控信息的znode
        node_monitor_record = self.kv_cfg.cfg_get_node_monitor()
        if node_monitor_record is None:
            self.kv_cfg.cfg_save_node_monitor(json.dumps(self.monitor_list))
            return
        # 创建监控信息
        node_monitor_json = json.loads(node_monitor_record)
        for new_monitor in self.monitor_list['Pool']:
            # 如果参数的pool一致
            update_flag = False
            for zk_monitor in node_monitor_json['Pool']:
                if new_monitor['PoolId'] == zk_monitor['PoolId']:
                    for cur_param in replace_list:
                        if cur_param in new_monitor:
                            zk_monitor[cur_param] = new_monitor[cur_param]
                    for cur_param in add_list:
                        if cur_param in new_monitor:
                            if cur_param in zk_monitor:
                                zk_monitor[cur_param] += new_monitor[cur_param]
                            else:
                                zk_monitor[cur_param] = new_monitor[cur_param]
                    update_flag = True
            # 如果旧的参数没该存储池
            if not update_flag:
                node_monitor_json['Pool'].append(copy.deepcopy(new_monitor))
        node_monitor_json['Backup'] = copy.deepcopy(self.monitor_list['Backup'])
        node_monitor_json['ZK'] = copy.deepcopy(self.monitor_list['ZK'])
        self.kv_cfg.cfg_save_node_monitor(json.dumps(node_monitor_json))

    def save_param_to_zks(self):
        replace_list = ['DataL1Hits', 'DataL2Hits', 'DataMisses']
        # 这几个值是每次只取得到累加值，而不是总量
        add_list = ['ReadIO', 'WriteIO', 'ReadByte', 'WriteByte', 'ReadLatency', 'WriteLatency']

        # 保存集群监控信息
        if self.is_pos_master:
            self.cfg.cfg_save_cluster_monitor(json.dumps(self.capacity_list))
        # 保存节点监控信息
        # 创建存放监控信息的znode
        node_monitor_record = self.cfg.cfg_get_node_monitor()
        if node_monitor_record is None:
            self.cfg.cfg_save_node_monitor(json.dumps(self.monitor_list))
            return
        # 创建监控信息
        node_monitor_json = json.loads(node_monitor_record)
        for new_monitor in self.monitor_list['Pool']:
            # 如果参数的pool一致
            update_flag = False
            for zk_monitor in node_monitor_json['Pool']:
                if new_monitor['PoolId'] == zk_monitor['PoolId']:
                    for cur_param in replace_list:
                        if cur_param in new_monitor:
                            zk_monitor[cur_param] = new_monitor[cur_param]
                    for cur_param in add_list:
                        if cur_param in new_monitor:
                            if cur_param in zk_monitor:
                                zk_monitor[cur_param] += new_monitor[cur_param]
                            else:
                                zk_monitor[cur_param] = new_monitor[cur_param]
                    update_flag = True
            # 如果旧的参数没该存储池
            if not update_flag:
                node_monitor_json['Pool'].append(copy.deepcopy(new_monitor))
        self.cfg.cfg_save_node_monitor(json.dumps(node_monitor_json))

    def get_iscsi_pool(self, StatsName):
        try:
            compile_ip = re.compile(r'/lun/(\d+)-(\d+)-(\d+)-(\d+)')
            result = compile_ip.search(StatsName)
            if result is not None:
                return int(result.group(1))
            else:
                return -1
        except Exception as e:
            self.log.error("get_iscsi_pool except: %s", repr(e))
            return -1

    def get_capacity_pool(self, StatsName):
        try:
            compile_ip = re.compile(r'/public/pool/(\d+)/cap_stats')
            result = compile_ip.search(StatsName)
            if result is not None:
                return int(result.group(1))
            else:
                return -1
        except Exception as e:
            self.log.error("get_capacity_pool except: %s", repr(e))
            return -1

    def get_capacity_disksn(self, StatsName):
        try:
            compile_ip = re.compile(r'/public/disk/(.*)/cap_stats')
            result = compile_ip.search(StatsName)
            if result is not None:
                return result.group(1)
            else:
                return None
        except Exception as e:
            self.log.error("get_capacity_disksn except: %s", repr(e))
            return None

    def monitor_param_init(self):
        self.monitor_list = {'Pool': [], 'Backup': {}, 'ZK': {}}
        self.capacity_list = {'Cluster': {}, 'Pool': [], 'Disk': {}}

    def monitor_param_cache_add(self, monitor_param):
        cur_param_list = ['DataL1Hits', 'DataL2Hits', 'DataMisses']
        # 依次列出已收集的所有存储池
        for pool_monitor in self.monitor_list['Pool']:
            # 与当前存储池的ID是否一致
            if pool_monitor['PoolId'] != monitor_param['PoolId']:
                continue
            # 依次列出所有指标
            for cur_param in cur_param_list:
                if cur_param in pool_monitor:
                    pool_monitor[cur_param] += monitor_param[cur_param]
                else:
                    pool_monitor[cur_param] = monitor_param[cur_param]
            # 已成功添加
            self.log.info("monitor_list = %s", repr(self.monitor_list))
            return
        self.monitor_list['Pool'].append(copy.deepcopy(monitor_param))
        self.log.info("monitor_list = %s", repr(self.monitor_list))

    def monitor_param_scsi_add(self, monitor_param):
        cur_param_list = ['ReadIO', 'WriteIO', 'ReadByte', 'WriteByte', 'ReadLatency', 'WriteLatency']
        latency_list = {'ReadLatency': 'ReadIO', 'WriteLatency': 'WriteIO'}
        # 依次列出已收集的所有存储池
        for pool_monitor in self.monitor_list['Pool']:
            # 与当前存储池的ID是否一致
            if pool_monitor['PoolId'] != monitor_param['PoolId']:
                continue
            # 依次列出所有指标
            for cur_param in cur_param_list:
                if cur_param in latency_list:
                    if cur_param in pool_monitor:
                        pool_monitor[cur_param] += monitor_param[cur_param] * monitor_param[latency_list[cur_param]]
                    else:
                        pool_monitor[cur_param] = monitor_param[cur_param] * monitor_param[latency_list[cur_param]]
                else:
                    if cur_param in pool_monitor:
                        pool_monitor[cur_param] += monitor_param[cur_param]
                    else:
                        pool_monitor[cur_param] = monitor_param[cur_param]
            # 已成功添加
            self.log.info("monitor_list = %s", repr(self.monitor_list))
            return
        add_monitor = copy.deepcopy(monitor_param)
        add_monitor['ReadLatency'] = add_monitor['ReadLatency'] * add_monitor['ReadIO']
        add_monitor['WriteLatency'] = add_monitor['WriteLatency'] * add_monitor['WriteIO']
        self.monitor_list['Pool'].append(add_monitor)
        self.log.info("monitor_list = %s", repr(self.monitor_list))

    def monitor_param_capacity_add(self, monitor_param):
        cur_param_list = ['UsedCap', 'TotalCap']
        self.capacity_list['Pool'].append(copy.deepcopy(monitor_param))
        for cur_param in cur_param_list:
            if cur_param in self.capacity_list['Cluster']:
                self.capacity_list['Cluster'][cur_param] += monitor_param[cur_param]
            else:
                self.capacity_list['Cluster'][cur_param] = monitor_param[cur_param]
        self.log.info("capacity_list = %s", repr(self.capacity_list))

    def monitor_param_backup_add(self, backup_info):
        self.monitor_list['Backup'] = backup_info

    def monitor_param_zk_add(self, zk_info):
        self.monitor_list['ZK'] = zk_info

    def monitor_param_add(self, monitor_param, monitor_type):
        if monitor_type == ParamType.TYPE_SCSI.value:
            self.monitor_param_scsi_add(monitor_param)
        elif monitor_type == ParamType.TYPE_CACHE.value:
            self.monitor_param_cache_add(monitor_param)
        elif monitor_type == ParamType.TYPE_CAPACITY.value:
            self.monitor_param_capacity_add(monitor_param)
        elif monitor_type == ParamType.TYPE_BACKUP.value:
            self.monitor_param_backup_add(monitor_param)
        elif monitor_type == ParamType.TYPE_ZK.value:
            self.monitor_param_zk_add(monitor_param)
        else:
            self.log.info("monitor parameter type error:%s", str(type))

    def monitor_param_get_iobyte(self, scsi):
        r_byte = 0
        w_byte = 0
        block_list = ['512', '1k', '2k', '4k', '8k', '16k', '32k', '64k', '128k', '256k', '512k', '1024k', '2048k']
        block_size_list = {'512': 512, '1k': 1024, '2k': 2048, '4k': 4096, '8k': 8192, '16k': 16384,
                           '32k': 32768, '64k': 65536, '128k': 130172, '256k': 262144, '512k': 524288,
                           '1024k': 1048576, '2048k': 2097152}
        for block in block_list:
            if block in scsi and 'Io' in scsi[block] and len(scsi[block]['Io']) == 2:
                r_byte += block_size_list[block] * scsi[block]['Io'][0]
                w_byte += block_size_list[block] * scsi[block]['Io'][1]
        return r_byte, w_byte

    def get_pos_rpc_ip(self):
        if self.hcicfg.is_hci():
            return self.cfg.get_node_ip()
        else:
            return "127.0.0.1"

    def save_capacity_param(self):
        if not self.is_pos_master:
            return
        rpcclient = pos_rpc.JSONRPCClient(addr=self.get_pos_rpc_ip(), port=5260)
        capacity_info = rpcclient.get_capacity_info()
        if capacity_info is None:
            return
        for cur_capacity in capacity_info:
            if 'StatsName' in cur_capacity and 'StatsInfo' in cur_capacity and \
                    'PoolStat' in cur_capacity['StatsInfo'] and \
                    self.get_capacity_pool(cur_capacity['StatsName']) >= 0:
                cur_poolid = self.get_capacity_pool(cur_capacity['StatsName'])
                cur_usecap = 0
                cur_totalcap = 0
                for cur_tier in cur_capacity['StatsInfo']['PoolStat']:
                    cur_usecap += cur_tier['UsedCapacity(GB)']
                    cur_totalcap += cur_tier['TotalCapacity(GB)']
                cur_cap_param = {'PoolId': self.cfg.get_pool_uuid(cur_poolid), 'UsedCap': cur_usecap,
                                 'TotalCap': cur_totalcap}
                self.monitor_param_add(cur_cap_param, ParamType.TYPE_CAPACITY.value)
            if 'StatsName' in cur_capacity and 'StatsInfo' in cur_capacity and \
                    'Nr_Scrub_Bad_Blocks' in cur_capacity['StatsInfo'] and \
                    'Nr_Scrub_UnRepair_Blocks' in cur_capacity['StatsInfo'] and \
                    'PoolId' in cur_capacity['StatsInfo']:
                disksn = self.get_capacity_disksn(cur_capacity['StatsName'])
                if disksn is None:
                    continue
                bad_block = cur_capacity['StatsInfo']['Nr_Scrub_Bad_Blocks']
                unrepair_block = cur_capacity['StatsInfo']['Nr_Scrub_UnRepair_Blocks']
                poolid = cur_capacity['StatsInfo']['PoolId']
                cur_cap_param = {'DiskSn': disksn, 'PoolId': poolid, 'BadBlock': bad_block,
                                 'UnrepairBlock': unrepair_block}
                self.capacity_list['Disk'][disksn] = copy.deepcopy(cur_cap_param)

    def save_remotebackup_param(self):
        backup_info = RemoteBackupJSONRPCClient.get_backup_state(self.get_pos_rpc_ip())
        if backup_info is None:
            return
        restore, backup = backup_info.Restore, backup_info.Backup
        bp_param = {
            'BP_PID': backup_info.ProcessID,
            MetricNode.BackupTotalIoNum.value: backup.TotalIoNum,
            MetricNode.BackupLastIoNum.value: backup.LastIoNum,
            MetricNode.BackupLastElapse.value: backup.LastElapse,
            MetricNode.BackupLastSize.value: backup.LastSize,
            MetricNode.RestoreTotalIoNum.value: restore.TotalIoNum,
            MetricNode.RestoreLastIoNum.value: restore.LastIoNum,
            MetricNode.RestoreLastElapse.value: restore.LastElapse,
            MetricNode.RestoreLastSize.value: restore.LastSize,
        }
        self.monitor_param_add(bp_param, ParamType.TYPE_BACKUP.value)

    def save_scsi_param(self):
        rpcclient = pos_rpc.JSONRPCClient(addr=self.get_pos_rpc_ip(), port=5260)
        scsi_info = rpcclient.get_scsi_info()
        if scsi_info is None:
            return
        for cur_scsi in scsi_info:
            if 'StatsName' in cur_scsi and 'StatsInfo' in cur_scsi and 'All' in cur_scsi['StatsInfo']:
                cur_poolid = self.get_iscsi_pool(cur_scsi['StatsName'])
                cur_readio = cur_scsi['StatsInfo']['All']['Io'][0]
                cur_writeio = cur_scsi['StatsInfo']['All']['Io'][1]
                cur_read_latency = cur_scsi['StatsInfo']['All']['AvgLatency'][0]
                cur_write_latency = cur_scsi['StatsInfo']['All']['AvgLatency'][1]
                cur_readbyte, cur_writebyte = self.monitor_param_get_iobyte(cur_scsi['StatsInfo'])
                cur_scsi_param = {'PoolId': self.cfg.get_pool_uuid(cur_poolid),
                                  'ReadIO': cur_readio, 'WriteIO': cur_writeio,
                                  'ReadByte': cur_readbyte, 'WriteByte': cur_writebyte,
                                  'ReadLatency': cur_read_latency, 'WriteLatency': cur_write_latency}
                self.monitor_param_add(cur_scsi_param, ParamType.TYPE_SCSI.value)

    def save_cache_param(self):
        rpcclient = pos_rpc.JSONRPCClient(addr=self.get_pos_rpc_ip(), port=5260)
        vdisk_info = rpcclient.get_cache_info()
        if vdisk_info is None:
            return
        for cur_cache in vdisk_info:
            if 'PoolId' in cur_cache and 'DataL1Hits' in cur_cache and \
                    'DataL2Hits' in cur_cache and 'DataMisses' in cur_cache:
                cur_cache_param = {'PoolId': self.cfg.get_pool_uuid(cur_cache['PoolId']),
                                   'DataL1Hits': cur_cache['DataL1Hits'],
                                   'DataL2Hits': cur_cache['DataL2Hits'],
                                   'DataMisses': cur_cache['DataMisses']}
                self.monitor_param_add(cur_cache_param, ParamType.TYPE_CACHE.value)

    def save_zk_param(self):
        try:
            if self.hcicfg.is_hci():
                return
            rpcclient = pos_rpc.JSONRPCEmeiClient(addr='127.0.0.1', port=9011)
            zk_info = rpcclient.call(method='get_zks_resource')
            if zk_info is None:
                return
        except Exception as e:
            self.log.warn(f"get zk param failed: {e}")
            return

        filter_key = ['nodeid', 'memory', 'maxmem', 'dirsize', 'maxdir']
        cur_zk_param = {k: v for k, v in zk_info.items() if k in filter_key}
        for k in filter_key:
            if cur_zk_param.get(k, None) is None:
                return
        self.monitor_param_add(cur_zk_param, ParamType.TYPE_ZK.value)

    def start(self):
        while True:
            try:
                # 判断是否已部署，如果未部署，不需要
                is_config = self.localcfg.is_config()
                if is_config == 0:
                    self.log.info("Current Node is not added")
                    time.sleep(self.monitor_cycle_s)
                    continue
                # 等待ZK连接
                if not self.cfg.is_zks_connect():
                    self.log.info("Current zk is not connect")
                    time.sleep(self.wait_conn_zks_time_s)
                    continue
                if self.kv_cfg is None:
                    self.kv_cfg = SocketKVpair(self.cfg.read_myid())
                # 清空临时参数
                self.monitor_param_init()
                # CAP参数采集
                self.master_sync()
                self.save_capacity_param()
                # backup参数采集
                self.save_remotebackup_param()
                # SCSI参数采集
                self.save_scsi_param()
                # CACHE参数采集
                self.save_cache_param()
                # ZK参数采集
                self.save_zk_param()
                # 采集数据保存到KVpair
                self.save_param_to_kv()
                time.sleep(self.monitor_cycle_s)
            except Exception as e:
                self.log.error("monitor process except (%s)", repr(e))
                import traceback
                self.log.error(traceback.format_exc())
                time.sleep(self.monitor_cycle_s)
