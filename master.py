# _*_ coding:utf-8 _*_
# refactor on:2020/9/21 15:11
# Author   :youweisheng

import zk_client
import logger
import exporter
import json
import time
import system_api
import copy
import config
import config_file
from exporter import Dimension
from exporter import MetricNode
from sock_kv import SocketKVpair


class Master(object):
    def __init__(self):
        self.log = logger.Logger()
        self.hcicfg = config.HciConfig()
        self.metric_node_list = [MetricNode.ReadIO.value, MetricNode.WriteIO.value, MetricNode.ReadByte.value,
                                 MetricNode.WriteByte.value, MetricNode.ReadLatency.value,
                                 MetricNode.WriteLatency.value, MetricNode.DataL1Hits.value,
                                 MetricNode.DataL2Hits.value, MetricNode.DataMisses.value]
        self.metric_bp_list = (MetricNode.BackupLastSize.value, MetricNode.BackupLastIoNum.value,
                               MetricNode.BackupLastElapse.value, MetricNode.BackupTotalIoNum.value,
                               MetricNode.RestoreLastSize.value, MetricNode.RestoreLastIoNum.value,
                               MetricNode.RestoreLastElapse.value, MetricNode.RestoreTotalIoNum.value)

        self.metric_cluster_list = [MetricNode.UsedCap.value, MetricNode.TotalCap.value]

        self.old_monitor = {'Cluster': {}, 'Pool': [], 'Node': []}  # 上一次监控采集指标(cache,scsi)
        self.new_monitor = {'Cluster': {}, 'Pool': [], 'Node': []}  # 本次监控采集指标(cache,scsi)
        self.diff_monitor = {'Cluster': {}, 'Pool': [], 'Node': []}  # 本次监控指标与上次监控指标的差值(cache,scsi)
        self.cluster_monitor = {'Cluster': {}, 'Pool': [], "Disk": {}}  # 本次capacity的监控采集指标
        self.old_cluster_monitor = {'Cluster': {}, 'Pool': [], "Disk": {}}  # 上次capacity的监控采集指标
        self.max_used_cap = 0
        self.current = {}  # 表示当前环境上的节点与存储池信息
        self.node_monitor_list = []  # 各节点采集信息汇总
        self.master_cycle_s = 10  # metrics的刷新时间
        self.wait_conn_zks_time_s = 1  # ZK断连的重试时间
        self.is_pos_master = False
        self.is_config = False
        self.exporter = exporter.Exporter()
        self.sys = system_api.SystemApi(5)
        self.localcfg = config_file.LocalNodeCfg()
        self.cfg = zk_client.ConfigCenter()
        self.kv_cfg = None
        self.history = None
        self.current_zk_cluster = []
        self.history_zk_cluster = []

    def get_param_offset(self, tag, tagid, monitor_list):
        listcnt = len(monitor_list)
        for i in range(listcnt):
            if monitor_list[i][tag] == tagid:
                return i
        return -1

    def get_history_node_and_pool(self):
        return self.history

    def get_current_node_and_pool(self):
        nodes_uuid = self.cfg.cfg_get_nodes_uuid()
        pools_uuid = self.cfg.cfg_get_pools_uuid()
        disks = self.cfg.cfg_get_disks()
        if nodes_uuid is None or pools_uuid is None:
            return None
        else:
            return {'Pool': pools_uuid, 'Node': nodes_uuid, "Disk": disks}

    # 初始化时，要保存当前的node与pool信息
    def update_history_pool_and_node(self):
        self.current = self.get_current_node_and_pool()
        if self.current is not None:
            self.history = copy.deepcopy(self.current)

    # 删除不存在的历史值
    def remove_noexist_history_metric(self):
        history = self.get_history_node_and_pool()
        self.current = self.get_current_node_and_pool()
        if history is None or self.current is None:
            # 如果当前值和历史值有一个不存在
            self.log.info("history = %s", repr(history))
            self.log.info("self.current = %s", repr(self.current))
            return
        for node in history['Node']:
            if node not in self.current['Node']:
                self.exporter.remove_metric(Dimension.NODE.value, node)
        for pool in history['Pool']:
            if pool not in self.current['Pool']:
                self.exporter.remove_metric(Dimension.POOL.value, pool)
        for history_zk in self.history_zk_cluster:
            if history_zk not in self.current_zk_cluster:
                self.exporter.remove_zk_metric(Dimension.IPADDR.value, history_zk)
        self.history_zk_cluster = copy.deepcopy(self.current_zk_cluster)

    def remove_all_metric(self):
        history = self.get_history_node_and_pool()
        if history is None:
            return False
        for node in history['Node']:
            self.exporter.remove_metric(Dimension.NODE.value, node)
        for pool in history['Pool']:
            self.exporter.remove_metric(Dimension.POOL.value, pool)
        self.exporter.remove_metric(Dimension.CLUSTER.value, '')
        for diskmsg in self.cluster_monitor['Disk']:
            disksn = self.cluster_monitor['Disk'][diskmsg]['DiskSn']
            poolid = self.cluster_monitor['Disk'][diskmsg]['PoolId']
            self.exporter.remove_disk_bad_block_metric(disksn, poolid)
            self.exporter.remove_disk_unrepair_block_metric(disksn, poolid)
        for history_zk in self.history_zk_cluster:
            self.exporter.remove_zk_metric(Dimension.IPADDR.value, history_zk)
        self.history_zk_cluster = []

    def is_old_master_null(self):
        for cur_param in self.metric_node_list:
            if cur_param in self.old_monitor['Cluster']:
                return False
        for cur_param in self.metric_bp_list:
            for node_info in self.old_monitor['Node']:
                if cur_param in node_info:
                    return False
        return True

    # 计算存储池的增量
    def pools_deviation_cal(self):
        for cur_pool in self.diff_monitor['Pool']:
            cur_new_poolid = cur_pool['PoolId']
            oldoff = self.get_param_offset('PoolId', cur_new_poolid, self.old_monitor['Pool'])
            if oldoff < 0:
                continue
            for metric in self.metric_node_list:
                # 该指标如果新节点有，旧节点没有，则不用做减法处理
                if metric not in self.old_monitor['Pool'][oldoff]:
                    continue
                # 该指标如果旧节点有，新节点没有，则报异常
                elif metric not in cur_pool:
                    return -1
                elif cur_pool[metric] < self.old_monitor['Pool'][oldoff][metric]:
                    cur_pool[metric] = 0
                else:
                    cur_pool[metric] = cur_pool[metric] - self.old_monitor['Pool'][oldoff][metric]

    # 计算节点的增量
    def nodes_deviation_cal(self):
        for cur_node in self.diff_monitor['Node']:
            cur_new_nodeid = cur_node['NodeId']
            oldoff = self.get_param_offset('NodeId', cur_new_nodeid, self.old_monitor['Node'])
            if oldoff < 0:
                continue

            def make_diff_for_metric(metric):
                # 该指标如果新节点有，旧节点没有，则不用做减法处理
                if metric not in self.old_monitor['Node'][oldoff]:
                    return 0
                # 该指标如果旧节点有，新节点没有，则报异常
                elif metric not in cur_node:
                    return -1
                cur_node[metric] = cur_node[metric] - self.old_monitor['Node'][oldoff][metric]

            old_bp_pid = self.old_monitor['Node'][oldoff].get("BP_PID", None)
            if old_bp_pid != cur_node.get("BP_PID", None):
                # 远程备份进程ID发生变化, 这次不上报
                for x in self.metric_bp_list:
                    x in cur_node and cur_node.pop(x)
            else:
                make_diff_for_metric(MetricNode.BackupTotalIoNum.value)
                if MetricNode.RestoreTotalIoNum.value in cur_node:
                    make_diff_for_metric(MetricNode.RestoreTotalIoNum.value)

            if "BP_PID" in cur_node:
                cur_node.pop("BP_PID")

            for metric in self.metric_node_list:
                # 该指标如果新节点有，旧节点没有，则不用做减法处理
                if metric not in self.old_monitor['Node'][oldoff]:
                    continue
                # 该指标如果旧节点有，新节点没有，则报异常
                elif metric not in cur_node:
                    return -1
                elif cur_node[metric] < self.old_monitor['Node'][oldoff][metric]:
                    cur_node[metric] = 0
                else:
                    cur_node[metric] = cur_node[metric] - self.old_monitor['Node'][oldoff][metric]

    # 计算集群的增量
    def cluster_deviation_cal(self):
        for metric in self.metric_node_list:
            # 该指标如果新节点有，旧节点没有，则不用做减法处理
            if metric not in self.old_monitor['Cluster']:
                continue
            # 该指标如果旧节点有，新节点没有，则报异常
            elif metric not in self.diff_monitor['Cluster']:
                return -1
            elif self.diff_monitor['Cluster'][metric] < self.old_monitor['Cluster'][metric]:
                self.diff_monitor['Cluster'][metric] = 0
            else:
                self.diff_monitor['Cluster'][metric] = self.diff_monitor['Cluster'][metric] \
                                                       - self.old_monitor['Cluster'][metric]

    # 保存用于计算差值的旧监控数据，该数据也可能为空
    def save_old_monitor(self):
        self.old_monitor = copy.deepcopy(self.new_monitor)

    # 如果当前不存在的指标，则不参与计算
    def save_new_monitor(self):
        self.new_monitor = {'Cluster': {}, 'Pool': [], 'Node': []}
        # 同步各节点的信息，并保存到self.new_monitor中
        self.log.info("node_monitor_list = %s", repr(self.node_monitor_list))
        for node_monitor in self.node_monitor_list:
            nodeid = node_monitor['NodeId']
            for pool_monitor in node_monitor['Pool']:
                poolid = pool_monitor['PoolId']
                node_offset = self.get_param_offset('NodeId', nodeid, self.new_monitor['Node'])
                pool_offset = self.get_param_offset('PoolId', poolid, self.new_monitor['Pool'])
                # 收集pool信息
                if pool_offset >= 0:
                    for cur_param in self.metric_node_list:
                        if cur_param not in pool_monitor:
                            continue
                        if cur_param in self.new_monitor['Pool'][pool_offset]:
                            self.new_monitor['Pool'][pool_offset][cur_param] += pool_monitor[cur_param]
                        else:
                            self.new_monitor['Pool'][pool_offset][cur_param] = pool_monitor[cur_param]
                else:
                    self.new_monitor['Pool'].append(copy.deepcopy(pool_monitor))
                # 收集node信息
                if node_offset >= 0:
                    for cur_param in self.metric_node_list:
                        if cur_param not in pool_monitor:
                            continue
                        if cur_param in self.new_monitor['Node'][node_offset]:
                            self.new_monitor['Node'][node_offset][cur_param] += pool_monitor[cur_param]
                        else:
                            self.new_monitor['Node'][node_offset][cur_param] = pool_monitor[cur_param]
                else:
                    add_monitor = copy.deepcopy(pool_monitor)
                    add_monitor.pop('PoolId')
                    add_monitor['NodeId'] = nodeid
                    self.new_monitor['Node'].append(copy.deepcopy(add_monitor))

            node_offset = self.get_param_offset('NodeId', nodeid, self.new_monitor['Node'])
            if node_offset >= 0:
                node = self.new_monitor['Node'][node_offset]
                backup = node_monitor['Backup']
                for x in backup:
                    node[x] = backup[x]
            else:
                add_monitor = copy.deepcopy(node_monitor['Backup'])
                add_monitor['NodeId'] = nodeid
                self.new_monitor['Node'].append(add_monitor)

        no_cal_to_cluster = self.metric_bp_list
        # 计算集群采集信息
        for node_monitor in self.new_monitor['Node']:
            for cur_param in self.metric_node_list:
                if cur_param not in node_monitor:
                    continue
                if cur_param in no_cal_to_cluster:
                    continue 
                if cur_param in self.new_monitor['Cluster']:
                    self.new_monitor['Cluster'][cur_param] += node_monitor[cur_param]
                else:
                    self.new_monitor['Cluster'][cur_param] = node_monitor[cur_param]

    # 将Counter的值减去旧值，gauge的值不变
    def create_diff_monitor(self):
        self.log.info("self.new_monitor = %s", repr(self.new_monitor))
        self.diff_monitor = copy.deepcopy(self.new_monitor)
        # 计算pool的增量
        self.pools_deviation_cal()
        # 计算node的增量
        self.nodes_deviation_cal()
        # 计算cluster的增量
        self.cluster_deviation_cal()
        self.log.info("self.diff_monitor = %s", repr(self.diff_monitor))
        return 0

    # 更新节点的监控指标
    def update_node_monitor_metric(self):
        # 更新值到exporter上
        self.current = self.get_current_node_and_pool()
        self.log.info("support pools and nodes = %s", repr(self.current))
        for metric in self.metric_node_list:
            if metric in self.diff_monitor['Cluster']:
                self.exporter.update_metric(metric, Dimension.CLUSTER.value, '',
                                            self.diff_monitor['Cluster'][metric])
            else:
                self.exporter.update_metric(metric, Dimension.CLUSTER.value, '', 0)
            for pool in self.diff_monitor['Pool']:
                if self.current is None or pool['PoolId'] not in self.current['Pool']:
                    continue
                # 该指标存在，如果获取到
                if metric in pool:
                    self.exporter.update_metric(metric, Dimension.POOL.value, pool['PoolId'], pool[metric])
                else:
                    self.exporter.update_metric(metric, Dimension.POOL.value, pool['PoolId'], 0)
            for node in self.diff_monitor['Node']:
                if self.current is None or node['NodeId'] not in self.current['Node']:
                    continue
                if metric in node:
                    self.exporter.update_metric(metric, Dimension.NODE.value, node['NodeId'], node[metric])
                else:
                    self.exporter.update_metric(metric, Dimension.NODE.value, node['NodeId'], 0)
        for metric in self.metric_bp_list:
            for node in self.diff_monitor['Node']:
                if self.current is None or node['NodeId'] not in self.current['Node']:
                    continue
                if metric in node:
                    self.exporter.update_metric(metric, Dimension.NODE.value, node['NodeId'], node[metric])
                else:
                    self.exporter.update_metric(metric, Dimension.NODE.value, node['NodeId'], 0)

    # 更新集群的监控指标
    def update_cluster_monitor_metric(self):
        # 更新集群采集的信息到exporter
        self.current = self.get_current_node_and_pool()
        for metric in self.metric_cluster_list:
            if metric in self.cluster_monitor['Cluster']:
                self.exporter.update_metric(metric, Dimension.CLUSTER.value, '',
                                            str(int(self.cluster_monitor['Cluster'][metric]) * (2 ** 30)))
            cur_use_cap = 0
            for pool in self.cluster_monitor['Pool']:
                if self.current is None or pool['PoolId'] not in self.current['Pool']:
                    continue
                if metric in pool:
                    self.exporter.update_metric(metric, Dimension.POOL.value, pool['PoolId'],
                                                str(int(pool[metric]) * (2 ** 30)))
                if metric == MetricNode.UsedCap.value:
                    cur_use_cap += int(pool[metric]) * (2 ** 30)
            if cur_use_cap > self.max_used_cap:
                self.max_used_cap = cur_use_cap
                self.exporter.update_metric(MetricNode.MaxUsedCap.value, Dimension.CLUSTER.value, 
                                            '', str(cur_use_cap))
        for diskmsg in self.cluster_monitor['Disk']:
            disksn = self.cluster_monitor['Disk'][diskmsg]['DiskSn']
            poolid = self.cluster_monitor['Disk'][diskmsg]['PoolId']
            bad_block = self.cluster_monitor['Disk'][diskmsg]['BadBlock']
            unrepair_block = self.cluster_monitor['Disk'][diskmsg]['UnrepairBlock']
            self.exporter.update_disk_bad_block_metric(disksn, poolid, bad_block)
            self.exporter.update_disk_unrepair_block_metric(disksn, poolid, unrepair_block)
        # 获取之前存在，但现在不存在的指标，或者poolID有变化的指标
        for diskmsg in self.old_cluster_monitor['Disk']:
            if diskmsg in self.cluster_monitor['Disk'] and self.old_cluster_monitor['Disk'][diskmsg]['PoolId'] \
                    == self.cluster_monitor['Disk'][diskmsg]['PoolId']:
                continue
            disksn = self.old_cluster_monitor['Disk'][diskmsg]['DiskSn']
            poolid = self.old_cluster_monitor['Disk'][diskmsg]['PoolId']
            self.exporter.remove_disk_bad_block_metric(disksn, poolid)
            self.exporter.remove_disk_unrepair_block_metric(disksn, poolid)

    # 检查是否未部署
    def deploy_check(self):
        # 判断是否已部署，如果未部署，不需要
        is_config = self.localcfg.is_config()
        if is_config == 0:
            self.log.info("Current Node is not added")
            # 如果当前节点被删除了
            if self.is_config is True:
                self.remove_all_metric()
                self.is_config = False
            return False
        self.is_config = True
        return True

    # 检查是否是主机
    def master_check(self):
        if not self.sys.is_master_node():
            self.log.info("Current Node is not master")
            # 如果主节点被切换出去，删除所有
            if self.is_pos_master is True:
                self.remove_all_metric()
                # 只有删除了才能设置该标识
                self.is_pos_master = False
            return False
        self.is_pos_master = True
        return True

    # 采集所有节点的监控指标
    def get_moniter_metrics_by_nodes(self):
        self.node_monitor_list = []
        node_list = self.kv_cfg.cfg_get_monitor_nodes()
        for nodeid in node_list:
            node_monitor = self.kv_cfg.cfg_get_node_monitor(myid=nodeid)
            if node_monitor is None:
                self.log.info("get node<%s> monitor failed", str(nodeid))
                time.sleep(self.master_cycle_s)
                continue
            node_param = json.loads(node_monitor)
            node_param['NodeId'] = self.cfg.get_node_uuid(str(nodeid))
            self.node_monitor_list.append(copy.deepcopy(node_param))
        # 采集集群
        cluster_monitor = self.kv_cfg.cfg_get_cluster_monitor()
        if cluster_monitor is None:
            self.log.info("get cluster monitor failed")
            time.sleep(self.master_cycle_s)
            return False
        self.old_cluster_monitor = copy.deepcopy(self.cluster_monitor)
        self.cluster_monitor = json.loads(cluster_monitor)
        return True
    
    def get_zk_monitor_by_node_id(self, nodeid):
        node_id = self.cfg.get_node_uuid(str(nodeid))
        for node_param in self.node_monitor_list:
            if node_param.get('NodeId', None) == node_id:
                return node_param.get("ZK")
        return None

    def update_zk_monitor(self):
        self.current_zk_cluster = []
        node_list = self.kv_cfg.cfg_get_monitor_nodes()
        for nodeid in node_list:
            zk_monitor = self.get_zk_monitor_by_node_id(nodeid)
            if not zk_monitor:
                continue
            ipaddr = self.sys.get_manage_ip(zk_monitor['nodeid'])
            self.exporter.update_metric(MetricNode.ZKMem.value, Dimension.IPADDR.value,
                                        ipaddr, str(zk_monitor['memory']))
            self.exporter.update_metric(MetricNode.ZKDir.value, Dimension.IPADDR.value,
                                        ipaddr, str(zk_monitor['dirsize']))
            self.exporter.update_metric(MetricNode.ZKMaxMem.value, Dimension.IPADDR.value,
                                        ipaddr, str(zk_monitor['maxmem']))
            self.exporter.update_metric(MetricNode.ZKMaxDir.value, Dimension.IPADDR.value,
                                        ipaddr, str(zk_monitor['maxdir']))
            self.current_zk_cluster.append(ipaddr)

    def start(self):
        while True:
            try:
                # 判断是否已部署，如果未部署，不需要
                if not self.deploy_check():
                    time.sleep(self.master_cycle_s)
                    continue
                # 等待ZK连接
                if not self.cfg.is_zks_connect():
                    self.log.info("Current zk is not connect")
                    time.sleep(self.wait_conn_zks_time_s)
                    continue
                if self.kv_cfg is None:
                    self.kv_cfg = SocketKVpair(self.cfg.read_myid())
                if not self.sys.is_mcast_server_running():
                    self.sys.start_mcast_server(self.cfg.get_nodes_ip)
                # 判断是否是主节点
                if not self.master_check():
                    time.sleep(self.master_cycle_s)
                    continue
                # 更新动态配置, HCI环境上不需要该操作
                if not self.hcicfg.is_hci():
                    svip = self.cfg.get_cluster_svip()
                    self.sys.update_pos_target(svip)
                # 获取各个节点采集的监控信息
                if not self.get_moniter_metrics_by_nodes():
                    continue
                # 备份旧的监控信息
                self.save_old_monitor()
                # 节点采集指标
                self.save_new_monitor()
                # 计算Counter指标差值
                if not self.is_old_master_null() and self.create_diff_monitor() == 0:
                    # 如果old_master不为空，表示不是第一次采集
                    # 如果有计算出合法差值，则表示有节点指标更新
                    self.update_node_monitor_metric()
                # 集群指标都有上送
                self.update_cluster_monitor_metric()
                # 上送ZK指标，HCI环境上不需要该操作
                if not self.hcicfg.is_hci():
                    self.update_zk_monitor()
                # 删除无用指标
                self.remove_noexist_history_metric()
                self.update_history_pool_and_node()
                time.sleep(self.master_cycle_s)
            except Exception as e:
                self.log.error("master exception:%s", repr(e))
                time.sleep(self.master_cycle_s)
