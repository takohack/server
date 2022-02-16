# _*_ coding:utf-8 _*_
# refactor on:2020/9/21 15:11
# Author   :youweisheng

from unicodedata import name
import logger
import config_file
from kazoo.client import KazooClient
from kazoo.retry import KazooRetry
from singleton import Singleton
import config
import json
import os
import re
import pickle
from enum import Enum


class ZKWatchType(Enum):
    DataWatch = 0
    ChildrenWatch = 1


class ZKWatchNode(object):
    def __init__(self, path, watch_type, watch):
        self.znode_path = path
        self.watch_type = watch_type
        self.znode_watch = watch


@Singleton
class ZKWatchList(object):
    def __init__(self):
        self.watch_list = []
        self.log = logger.Logger()

    def add(self, path, watch_type, watch):
        self.watch_list.append(ZKWatchNode(path, watch_type, watch))
        self.log.info("watch list add: %s", path)

    def remove(self, path, watch_type):
        for node in self.watch_list[:]:
            if node.znode_path == path and node.watch_type == watch_type:
                self.watch_list.remove(node)
                self.log.info("watch list remove: %s", path)

    def get(self, path, watch_type):
        for node in self.watch_list[:]:
            if node.znode_path == path and node.watch_type == watch_type:
                return node.znode_watch
        return None

    def exists(self, path, watch_type):
        for node in self.watch_list[:]:
            if node.znode_path == path and node.watch_type == watch_type:
                return True
        return False

    def getall(self):
        return self.watch_list[:]


class ZKClient(object):
    def __init__(self):
        self.zk_client = ''
        self.zk_state = ''
        self.log = logger.Logger()
        self.connect_lost_flag = True
        self.zk_watch = ZKWatchList()

    def set_state(self, state):
        self.zk_state = state

    def get_state(self):
        return self.zk_state

    def get_stat_info(self,path):
        return self.zk_client.get_acls(path)

    # 获取指定ZNode信息
    def get(self, node, need_stat=False):
        self.zk_client.exists(node)
        data, stat = self.zk_client.get(node)
        if need_stat:
            return data, stat
        else:
            return data

    # 获取指定ZNode信息
    def create(self, node, data, ephemeral=False, sequence=False):
        self.log.info("zkclient create node=%s,data=%s", node, data)
        self.zk_client.create(node, data, ephemeral=ephemeral, sequence=sequence)

    # 获取指定ZNode信息
    def delete(self, node):
        self.log.info("zkclient delete node=%s", node)
        self.zk_client.exists(node)
        self.zk_client.delete(node, recursive=True)

    # 获取指定ZNode信息
    def set(self, node, data):
        if self.zk_client.exists(node):
            self.log.info("zkclient set node=%s,data=%s", node, data)
            self.zk_client.set(node, data)
        else:
            self.log.warning("node(%s) not exist when do zk set", node)

    # 递归创建所有层级的节点
    def ensure_path(self, node):
        self.log.info("zkclient ensure_path node=%s", node)

        self.zk_client.ensure_path(node)

    # 返回子节点信息
    def get_children(self, node):
        children = self.zk_client.get_children(node)
        return children

    # ZnodeStat of the node if it exists, else None if the node does not exist.
    def exists(self, node):
        znode_status = self.zk_client.exists(node)
        return znode_status

    def election(self, path, myid):
        return self.zk_client.Election(path, myid)

    def lock(self, path):
        return self.zk_client.Lock(path)

    # 连接到zkserver客户端端口,#创建一个客户端，可以指定多台zookeeper
    def connettozkserver(self, zkhosts, connection_listener):
        try:
            retry = KazooRetry(max_tries=-1, backoff=1)  # 退避参数由默认值2改成1，可以减少重连的等待时间
            self.zk_client = KazooClient(
                hosts=zkhosts,
                timeout=4.0,  # 连接超时时间
                connection_retry=retry,  # 连接重试
                logger=logger.Logger()  # 传一个日志对象进行，方便 输出debug日志
            )
            self.zk_client.add_listener(connection_listener)
            self.log.info("zkclient connettozkserver zk_client.start()")
            self.zk_client.start()

        except Exception as e:
            self.log.error("Cannot connect to Zookeeper: {0}".format(e))
            self.zk_state = "CLOSED"
            self.log.error("Cannot connect to Zookeeper zk_state=%s", self.zk_state)

    # 关闭zk
    def closetozkserver(self):
        try:
            # 重置标志位
            self.zk_state = "CLOSED"

            # 关闭zk客户端
            if self.zk_client != '':
                self.zk_client.stop()
                self.zk_client.close()
                self.zk_client = ''

        except Exception as e:
            self.log.error("closetozkserver: {0}".format(e))

    def connection_listener(self, state):
        self.log.info("exporter recv zks event, zkstate=%s", repr(state))
        self.zk_state = state

    def is_zks_connect(self):
        if self.zk_state == "CONNECTED":
            return True
        else:
            return False

    def remove_watch(self, node, watch_type):
        try:
            watch = self.zk_watch.get(node, watch_type)
            if watch is not None:
                watch._client.remove_listener(watch._session_watcher)
                self.zk_watch.remove(node, watch_type)
        except Exception as e:
            self.log.error("remove watch <%s> except: %s", node, repr(e))

    def register_datawatch(self, node, znode_monitor):
        self.remove_watch(node, ZKWatchType.DataWatch.value)
        datawatch = self.zk_client.DataWatch(node)
        self.zk_watch.add(node, ZKWatchType.DataWatch.value, datawatch)

        @datawatch
        def watch_node(watch_data, watch_stat):
            znode_monitor(watch_data, watch_stat)

    def register_childwatch(self, node, znode_monitor):
        self.remove_watch(node, ZKWatchType.ChildrenWatch.value)
        childwatch = self.zk_client.ChildrenWatch(node)
        self.zk_watch.add(node, ZKWatchType.ChildrenWatch.value, childwatch)

        @childwatch
        def watch_children(childrens):
            znode_monitor(childrens)

    def remove_listener(self, connect_listener):
        return self.zk_client.remove_listener(connect_listener)
# show pos 添加
#定义一个类保持node的状态信息
class Node:
    def __init__(self,myid,nodeid,mnetip,snetip,status,type):
        self.myid = myid
        self.nodeid = nodeid
        self.mnetip = mnetip
        self.snetip = snetip
        self.status = status
        self.type = type
        self.is_arbitrate = 'No'        
    
    def __str__(self) -> str:
        if self.type == 'arbitrate':
            self.is_arbitrate = 'Yes'
        return self.myid +"---"+ self.nodeid+ "---"+ self.mnetip + "---" + self.snetip + "---" + self.status + "---" + self.is_arbitrate


class BaseConfigCenter(object):
    def __init__(self, zk_client):
        self.pos_masterid_path = "/pos/service/P_Deployer_Node/master_election"
        self.zk_client = zk_client
        self.log = logger.Logger()
        self.hcicfg = config.HciConfig()
        self.localcfg = config_file.LocalNodeCfg()
        self.zk_watch = ZKWatchList()
        self.resource_cache = "./cache.json"

    def set_state(self, state):
        self.zk_client.set_state(state)

    def get_state(self):
        return self.zk_client.get_state()

    def connettozkserver(self, zkhosts, connection_listener):
        return self.zk_client.connettozkserver(zkhosts, connection_listener)

    def closetozkserver(self):
        return self.zk_client.closetozkserver()

    def is_zks_connect(self):
        return self.zk_client.is_zks_connect()
    
    #show pos 添加
    #获取管理网虚拟ip地址
    def get_cluster_mvip(self):
        cluster_mvip_path = '/pos/cluster/orchestration/net/vip/network_mvip'
        mvip = self.zk_client.get(cluster_mvip_path).decode('utf-8')
        return mvip


    #取当前集群的Cluster id
    def get_cluster_id(self):
        clusterid_path = "/pos/cluster"
        if self.zk_client.exists(clusterid_path) is None:
            return -1
        clusterid = self.zk_client.get(clusterid_path).decode('utf-8')
        return clusterid
    #给定myid判断node类型
    def get_nodetype(self,myid):
        normal_node_path = '/pos/cluster/nodes/' + str(myid)
        arbitrate_node_path = '/pos/cluster/arbitrate/' + str(myid)
        if self.zk_client.exists(normal_node_path):
            return 'normal'
        elif self.zk_client.exists(arbitrate_node_path):
            return 'arbitrate'
        else:
            return -1
    #判断节点是否在线
    def check_node_online(self,myid,judge_type):
        uuid =  self.get_node_uuid(myid)
        pos_tmp_path = '/pos/service/P_Deployer_Node/joined_node'
        pd_tmp_path = '/pos/service/P_Deployer/joined_node'
        if judge_type == 'normal':
            if not self.zk_client.exists(pos_tmp_path):
                return False
            pos_nodes = self.zk_client.get_children(pos_tmp_path)
            if uuid in pos_nodes:
                return True
            else:
                return False
        elif judge_type == 'arbitrate':
            if not self.zk_client.exists(pd_tmp_path):
                return False
            pd_nodes = self.zk_client.get_children(pd_tmp_path)
            if uuid in pd_nodes:
                return True
            else:
                return False
        else:
            return -1
        
    #获取节点的状态
    def get_nodestatus(self,myid):
        node_type = self.get_nodetype(myid)
        if node_type == 'normal':
            if self.check_node_online(myid,'normal'):
                return 'Online'
            else:
                return 'Offline'
        elif node_type == 'arbitrate':
            if self.check_node_online(myid,'arbitrate'):
                return 'Online'
            else:
                return 'Offline'
        else:
            return -1

    #获取节点的SnetIp
    def get_nodesnetip(self,myid):
        snetip_path = '/pos/cluster/nodes/'+ str(myid) + '/net/network_interface/network_ip'
        if self.zk_client.exists(snetip_path):
            snet_ip = self.zk_client.get(snetip_path).decode('utf-8')
            return snet_ip
        else:
            return -1
    #获取节点的MnetIp

    #对外提供获取集群nodes信息
    def get_nodes_info(self):
        normal_nodes = self.get_normal_nodes()
        nodes_info = []
        for node in normal_nodes:
            node_uuid = self.get_node_uuid(node)
            node_MnetIp = self.get_cluster_mvip()
            node_SnetIp = self.get_nodesnetip(node)
            node_status = self.get_nodestatus(node)
            node_type = self.get_nodetype(node)
            temp_node = Node(node,node_uuid,node_MnetIp,node_SnetIp,node_status,node_type)
            nodes_info.append(temp_node)
        return nodes_info

    #获取znode类型(用在获取存储池信息)
    def vertify_znode_type(self,znode,type):
        rules = {
            "pool":"Pool-(?P<poolid>\d+)",
            "vdisk": "Vdisk-(?P<vdiskid>\d+)",
            "volume": "Volume-(?P<volumeid>\d+)"
        }
        rule = rules[type]

        if re.match(rule,znode):
            return True
        else:
            return False 

    #获取存储池信息
    def get_pools_info(self):
        if self.zk_client.exists('/pos/storage_cluster/state-view'):
            pools_info = []
            pools = self.zk_client.get_children('/pos/storage_cluster/state-view')
            for pool in pools:
                pool_info = {}
                if self.vertify_znode_type(pool,'pool'):
                    pool_msg = self.zk_client.get('/pos/storage_cluster/state-view/%s' % pool)
                    pool_msg = json.loads(pool_msg)
                    pool_info['UsedCapacity'] = pool_msg['UsedCapacity']
                    pool_info['TotalCapacity'] = pool_msg['TotalCapacity']
                    pools_info.append(pool_info)
            return pools_info
        else:
            return -1
    
    #获取vdisk数量
    def get_vdisk_num(self):
        if self.zk_client.exists('/pos/storage_cluster/config-view'):
            vdisk_num = 0
            pools = self.zk_client.get_children('/pos/storage_cluster/config-view')
            for pool in pools:
                if self.vertify_znode_type(pool,'pool'):      #先判断znode是不是pool
                    vdisk_info = self.zk_client.get_children('/pos/storage_cluster/config-view/%s' % pool)
                    for vdisk in vdisk_info:
                        if self.vertify_znode_type(vdisk,'vdisk'): #在判断znode是不是vdisk
                            vdisk_num += 1
            return vdisk_num
        else:
            return -1

    #获取Iscsi Target数量:
    def get_iscsi_num(self):
        if self.zk_client.exists('/pos/storage_cluster/iscsi/config_view'):
            iscsis = self.zk_client.get_children('/pos/storage_cluster/iscsi/config_view')
            return len(iscsis)

    def get_pd_master(self):
        def get_cZxid(outer,znode):
            stat_info = outer.zk_client.get_stat_info('/pos/service/P_Deployer/Master_election/%s' % znode)
            stat_info = list(stat_info)[1]
            return stat_info.czxid

        if self.zk_client.exists('/pos/service/P_Deployer/Master_election'):
            znodes = self.zk_client.get_children('/pos/service/P_Deployer/Master_election')
            pd_master = self.zk_client.get('/pos/service/P_Deployer/Master_election/%s' % znodes[0]).decode('utf-8')
            min_cZxid = get_cZxid(self,znodes[0])
            for i in range(len(znodes)):
                if get_cZxid(self,znodes[i]) < min_cZxid:
                    min_cZxid = get_cZxid(self,znodes[i])
                    pd_master = self.zk_client.get('/pos/service/P_Deployer/Master_election/%s' % znodes[i]).decode('utf-8')
            return pd_master

    #根据id查询resoucese
    def get_pool_byid(self,query_info):
        pool_id = query_info[0]
        pool_configview_path = "/pos/storage_cluster/config-view/Pool-"+pool_id
        pool_stateview_path = "/pos/storage_cluster/state-view/Pool-"+pool_id
        pool_info = {"config_view":"N/A","state_view":"N/A"}
        if self.zk_client.exists(pool_configview_path):
            config_view = self.zk_client.get(pool_configview_path).decode('utf-8')
            pool_info['config_view'] = config_view
        if self.zk_client.exists(pool_stateview_path):
            state_view = self.zk_client.get(pool_stateview_path).decode('utf-8')
            pool_info['state_view'] = state_view
        return pool_info

    def get_vdisk_byid(self,query_info):
        pool_id = query_info[0]
        vdisk_id = query_info[1]
        vdisk_configview_path = "/pos/storage_cluster/config-view/Pool-"+pool_id+"/Vdisk-"+vdisk_id
        vdisk_stateview_path = "/pos/storage_cluster/state-view/Pool-"+pool_id+"/Vdisk-"+vdisk_id
        vdisk_info = {"config_view":"N/A","state_view":"N/A"}
        if self.zk_client.exists(vdisk_configview_path):
            config_view = self.zk_client.get(vdisk_configview_path).decode('utf-8')
            vdisk_info['config_view'] = config_view
        if self.zk_client.exists(vdisk_stateview_path):
            state_view = self.zk_client.get(vdisk_stateview_path).decode('utf-8')
            vdisk_info['state_view'] = state_view
        return vdisk_info
    
    def get_volume_byid(self,query_info):
        pool_id = query_info[0]
        vdisk_id = query_info[1]
        volume_id = query_info[2]
        volume_configview_path = "/pos/storage_cluster/config-view/Pool-"+pool_id+"/Vdisk-"+vdisk_id+"/Volume-"+volume_id
        volume_stateview_path = "/pos/storage_cluster/state-view/Pool-"+pool_id+"/Vdisk-"+vdisk_id+"/Volume-"+volume_id
        volume_info = {"config_view":"N/A","state_view":"N/A"}
        if self.zk_client.exists(volume_configview_path):
            config_view = self.zk_client.get(volume_configview_path).decode('utf-8')
            volume_info['config_view'] = config_view
        if self.zk_client.exists(volume_stateview_path):
            state_view = self.zk_client.get(volume_stateview_path).decode('utf-8')
            volume_info['state_view'] = state_view
        return volume_info

    def get_snapshot_byid(self,query_info):
        pool_id = query_info[0]
        vdisk_id = query_info[1]
        volume_id = query_info[2]
        snapshot_id = query_info[3]
        snapshot_configview_path = "/pos/storage_cluster/config-view/Pool-"+pool_id+"/Vdisk-"+vdisk_id+"/Volume-"+volume_id+"/Snapshot-"+snapshot_id
        snapshot_stateview_path = "/pos/storage_cluster/state-view/Pool-"+pool_id+"/Vdisk-"+vdisk_id+"/Volume-"+volume_id+"/Snapshot-"+snapshot_id
        snapshot_info = {"config_view":"N/A","state_view":"N/A"}
        if self.zk_client.exists(snapshot_configview_path):
            config_view = self.zk_client.get(snapshot_configview_path).decode('utf-8')
            snapshot_info['config_view'] = config_view
        if self.zk_client.exists(snapshot_stateview_path):
            state_view = self.zk_client.get(snapshot_stateview_path).decode('utf-8')
            snapshot_info['state_view'] = state_view
        return snapshot_info
    
    def get_children_bypath(self,path):
        if self.zk_client.exists(path):
            return self.zk_client.get_children(path)
        else:
            return -1

    def get_znode_info(self,path):
        if self.zk_client.exists(path):
            return self.zk_client.get(path)
        else:
            return -1

    def get_pool_byname(self,resourcename):
        def search_item_fromzk(outer,flag):
            pool_info = {"config_view":"N/A","state_view":"N/A","resource_id":[-1,-1,-1]}
            pool_node_path = "/pos/storage_cluster/config-view"
            pool_znodes = outer.get_children_bypath(pool_node_path)
            if pool_znodes != -1:
                if flag:
                    resource_cache = open(outer.resource_cache,'w')
                    cache_json = {}
                for znode in pool_znodes:
                    if outer.vertify_znode_type(znode,'pool'):
                        znode_info_path = "/pos/storage_cluster/config-view/"+znode
                        znode_info = outer.get_znode_info(znode_info_path).decode('utf-8')
                        if znode_info != -1:
                            znode_name = outer.get_view_name(znode_info)
                            znode_id = outer.get_view_id(znode_info)
                            saved_id = outer.list_to_resourceid(znode_id)
                            cache_json[saved_id] = znode_name
                            if znode_name == resourcename:  #找到了
                                pool_info = self.get_pool_byid(znode_id)
                                pool_info["resource_id"] = znode_id
                                if flag:
                                    continue
                                else:
                                    #找到了就不用再继续找了
                                    json.dump(cache_json,resource_cache)
                                    return pool_info
            json.dump(cache_json,resource_cache)
            return pool_info

        if os.path.exists(self.resource_cache) and os.path.getsize(self.resource_cache):
            resource_cache = open(self.resource_cache)   
            cache_json = json.load(resource_cache)
            for key,value in cache_json.items():
                if value == resourcename:  #cache命中
                    resource_id = key
                    query_info = resource_id.split('-')
                    pool_zookeeper = self.get_pool_byid(query_info)
                    pool_name_fromzkview = self.get_view_name(pool_zookeeper["config_view"])
                    if pool_name_fromzkview == resourcename:
                        pool_zookeeper["resource_id"] = query_info
                        return pool_zookeeper
                    else: #cahche的资源已经发生了变化
                        return search_item_fromzk(self,False)
                #有pool但没有对应的name 或者 有对应name但在zookeeper中已发生变化
        #这里开始是从zookeeper中遍历查询name
        return search_item_fromzk(self,True)
        
        
            
            

    def list_to_resourceid(self,id_list):
        str = '-'
        return str.join(id_list)

    def get_view_id(self,view):
        id_list = []
        json_obj = json.loads(view)
        view_arributes = json_obj.get("attributes")
        pool_id = view_arributes.get("PoolId")
        vdisk_id = view_arributes.get("VdiskId")
        volume_id = view_arributes.get("VolumeId")
        if pool_id != None:
            id_list.append(str(pool_id))
        if vdisk_id != None:
            id_list.append(str(vdisk_id))
        if volume_id != None:
            id_list.append(str(volume_id))
        return id_list
    def get_view_name(self,view):
        pool_msg = json.loads(view)
        return pool_msg["attributes"]["Name"]

    #end show pos 添加
    
    # 取当前节点的路径
    def get_nodes_path(self, myid=None):
        if myid is None:
            myid = str(self.read_myid())
        if self.localcfg.is_arbitrate_node():
            return "/pos/cluster/arbitrate/%s" % myid
        else:
            return "/pos/cluster/nodes/%s" % myid

    # 获取本节点uuid形式的节点id
    def get_node_uuid(self, myid=None):
        nodepath = self.get_nodes_path(myid)
        if self.zk_client.exists(nodepath) is None:
            return -1
        nodeid = self.zk_client.get(nodepath).decode('utf-8')
        return nodeid

    def cfg_save_node_monitor(self, value):
        mymonitor = "/pos/service/exporter/nodes/%s/monitor" % str(self.read_myid())
        if not self.zk_client.exists(mymonitor):
            self.zk_client.ensure_path(mymonitor)
        self.zk_client.set(mymonitor, str(value).encode('utf-8'))

    def cfg_get_node_monitor(self, myid=0):
        if myid == 0:
            myid = self.read_myid()
        mymonitor = "/pos/service/exporter/nodes/%s/monitor" % str(myid)
        if self.zk_client.exists(mymonitor):
            return self.zk_client.get(mymonitor).decode('utf-8')
        return None

    def cfg_save_cluster_monitor(self, value):
        mymonitor = "/pos/service/exporter/cluster/monitor"
        if not self.zk_client.exists(mymonitor):
            self.zk_client.ensure_path(mymonitor)
        self.zk_client.set(mymonitor, str(value).encode('utf-8'))

    def cfg_get_cluster_monitor(self):
        mymonitor = "/pos/service/exporter/cluster/monitor"
        if self.zk_client.exists(mymonitor):
            return self.zk_client.get(mymonitor).decode('utf-8')
        return None

    def cfg_save_monitor_history(self, value):
        history = "/pos/service/exporter/history"
        if not self.zk_client.exists(history):
            self.zk_client.ensure_path(history)
        self.zk_client.set(history, str(value).encode('utf-8'))

    def cfg_get_monitor_history(self):
        history = "/pos/service/exporter/history"
        if self.zk_client.exists(history):
            return self.zk_client.get(history).decode('utf-8')
        return None

    def cfg_get_monitor_nodes(self):
        if self.zk_client.exists("/pos/service/exporter/nodes"):
            return self.zk_client.get_children("/pos/service/exporter/nodes")
        else:
            return []

    def get_arbitrates_nodes(self):
        arbitrates = []
        if self.zk_client.exists('/pos/cluster/arbitrate'):
            arbitrates = self.zk_client.get_children('/pos/cluster/arbitrate')
        return arbitrates

    def get_normal_nodes(self):
        nodes = []
        if self.zk_client.exists('/pos/cluster/nodes'):
            nodes = self.zk_client.get_children('/pos/cluster/nodes')
        return nodes

    def get_nodes_uuid(self):
        children = self.get_normal_nodes()
        arbitrates = self.get_arbitrates_nodes()
        nodes_uuid = []
        for sub in children:
            node_path = '/pos/cluster/nodes/' + sub
            node_uuid = self.zk_client.get(node_path).decode('utf-8')
            nodes_uuid.append(node_uuid)
        for sub in arbitrates:
            node_path = '/pos/cluster/arbitrate/' + sub
            node_uuid = self.zk_client.get(node_path).decode('utf-8')
            nodes_uuid.append(node_uuid)
        return nodes_uuid

    # 获取所有节点的uuid
    def cfg_get_nodes_uuid(self):
        try:
            children = self.get_normal_nodes()
            arbitrates = self.get_arbitrates_nodes()
            nodes_uuid = []
            for sub in children:
                node_path = '/pos/cluster/nodes/' + sub
                node_uuid = self.zk_client.get(node_path).decode('utf-8')
                nodes_uuid.append(node_uuid)
            for sub in arbitrates:
                node_path = '/pos/cluster/arbitrate/' + sub
                node_uuid = self.zk_client.get(node_path).decode('utf-8')
                nodes_uuid.append(node_uuid)
            return nodes_uuid
        except Exception as e:
            self.log.info("get nodes uuid except: %s", repr(e))
            return None

    # 获取所有pool的uuid
    def cfg_get_pools_uuid(self):
        try:
            pools_uuid = []
            if self.zk_client.exists('/pos/storage_cluster/config-view'):
                pools = self.zk_client.get_children('/pos/storage_cluster/config-view')
                for pool in pools:
                    pool_msg = self.zk_client.get('/pos/storage_cluster/config-view/%s' % pool)
                    pool_msg = json.loads(pool_msg)
                    pools_uuid.append(pool_msg['attributes']['Name'])
            return pools_uuid
        except Exception as e:
            self.log.info("get pools uuid except: %s", repr(e))
            return None

    def cfg_get_disks(self):
        try:
            disks = []
            if self.zk_client.exists('/pos/service/papiserver/cfgcenter/snspace'):
                disks = self.zk_client.get_children('/pos/service/papiserver/cfgcenter/snspace')
            return disks
        except Exception as e:
            self.log.info("get disks except: %s", repr(e))
            return None

    def get_pos_masterid(self):
        if self.zk_client.exists(self.pos_masterid_path):
            data = self.zk_client.get(self.pos_masterid_path)
            pos_masterid = data.decode('utf-8').split('\0')[0]
            return pos_masterid
        else:
            return -1

    # 获取uuid形式的存储池id
    def get_pool_uuid(self, poolid):
        pool_cfg_view_path = '/pos/storage_cluster/config-view/Pool-' + str(poolid)
        if self.zk_client.exists(pool_cfg_view_path) is None:
            self.log.info("pool_cfg_view_path no exist")
            return None
        pool_cfg_view = self.zk_client.get(pool_cfg_view_path).decode('utf-8')
        pool_cfg_view_json = json.loads(pool_cfg_view)
        if 'attributes' in pool_cfg_view_json and 'Name' in pool_cfg_view_json['attributes']:
            return pool_cfg_view_json['attributes']['Name']
        self.log.info("pool_cfg_view_path no exist")
        return None

    # 获取存储虚拟ip地址
    def get_cluster_svip(self):
        cluster_svip_path = '/pos/cluster/orchestration/net/vip/network_svip'
        svip = self.zk_client.get(cluster_svip_path).decode('utf-8')
        return svip

    # 获取集群节点IP信息
    def get_nodes_ip(self):
        children = self.get_normal_nodes()
        arbitrates = self.get_arbitrates_nodes()
        self.log.info("zkclient get_nodes_ip children=%s", children)
        nodes_ip = []
        for sub in children:
            self.log.info("zkclient get_nodes_ip children=%s", sub)
            ippath = '/pos/cluster/nodes/' + sub + '/net/network_interface/network_ip'
            ip = self.zk_client.get(ippath)
            nodes_ip.append(ip.decode('utf-8'))
        for sub in arbitrates:
            self.log.info("zkclient get_nodes_ip children=%s", sub)
            ippath = '/pos/cluster/arbitrate/' + sub + '/net/network_interface/network_ip'
            ip = self.zk_client.get(ippath)
            nodes_ip.append(ip.decode('utf-8'))
        self.log.info("zkclient get_nodes_ip nodes_ip=%s", json.dumps(nodes_ip))
        return nodes_ip

    def get_cur_nodes_path(self):
        # mark 后续HCI有仲裁节点时，这个地方记得改
        return "/pos/cluster/nodes/%s" % str(self.read_myid())

    # 获取集群节点IP信息
    def get_node_ip(self):
        node_ip_path = '%s/net/network_interface/network_ip' % self.get_cur_nodes_path()
        ip_address = self.zk_client.get(node_ip_path).decode('utf-8')
        return ip_address

    # 获取集群节点信息
    def get_nodes(self):
        nodes = self.get_normal_nodes()
        arbitrates = self.get_arbitrates_nodes()
        nodes.extend(arbitrates)
        return nodes

    def get_other_nodes_path(self, nodeid):
        nodes = self.get_normal_nodes()
        arbitrates = self.get_arbitrates_nodes()
        if str(nodeid) in arbitrates:
            return "/pos/cluster/arbitrate/%s" % str(nodeid)
        elif str(nodeid) in nodes:
            return "/pos/cluster/nodes/%s" % str(nodeid)
        else:
            self.log.error("get nodes<%s> failed", nodeid)
            return "/pos/cluster/nodes/%s" % str(nodeid)

    # nodeid(uuid)转myid
    def nodeid2myid(self, nodeid):
        myid_list = self.get_nodes()
        for myid in myid_list:
            nodeid_path = self.get_other_nodes_path(myid)
            nodeid_i = self.zk_client.get(nodeid_path).decode("utf-8")
            if str(nodeid_i) == str(nodeid):
                return myid

        self.log.warning("can not find nodeid(%s) in cluster", str(nodeid))
        return -1

    def read_myid(self):
        if self.hcicfg.is_hci():
            nodeuuid = os.getenv('POS_HOST_ID')
            return self.nodeid2myid(nodeuuid)
        else:
            return self.localcfg.read_myid()

    # 保存告警的状态
    def save_alert_status(self, alertname):
        alert_status_fpath = '/pos/service/exporter/alert/status'
        alert_status_path = '/pos/service/exporter/alert/status/%s' % alertname
        if not self.zk_client.exists(alert_status_fpath):
            self.zk_client.ensure_path(alert_status_fpath)
        if not self.zk_client.exists(alert_status_path):
            self.zk_client.create(alert_status_path, b'')
        else:
            self.zk_client.set(alert_status_path, b'')

    # 清除告警的状态
    def del_alert_status(self, alertname):
        alert_status_path = '/pos/service/exporter/alert/status/%s' % alertname
        if self.zk_client.exists(alert_status_path):
            self.zk_client.delete(alert_status_path)

    def is_alert_status_exist(self, alertname):
        alert_status_path = '/pos/service/exporter/alert/status/%s' % alertname
        if self.zk_client.exists(alert_status_path):
            return True
        else:
            return False

    def get_alert_status_list(self):
        alert_status_path = '/pos/service/exporter/alert/status'
        if self.zk_client.exists(alert_status_path):
            return self.zk_client.get_children(alert_status_path)
        else:
            return []

    def alert_event_init(self):
        alert_event_fpath = '/pos/service/exporter/alert/event'
        if not self.zk_client.exists(alert_event_fpath):
            self.zk_client.ensure_path(alert_event_fpath)

    # 创建告警的事件
    def create_alert_event(self, event):
        alert_event_fpath = '/pos/service/exporter/alert/event'
        alert_event_path = '/pos/service/exporter/alert/event/msg-'
        if not self.zk_client.exists(alert_event_fpath):
            self.zk_client.ensure_path(alert_event_fpath)
        self.zk_client.create(alert_event_path, event.encode('utf-8'), sequence=True)

    # 获取告警事件
    def get_alert_event(self, event_name):
        alert_event_path = '/pos/service/exporter/alert/event/%s' % event_name
        return self.zk_client.get(alert_event_path).decode('utf-8')

    # 获取告警事件列表
    def get_alert_event_list(self):
        alert_event_fpath = '/pos/service/exporter/alert/event'
        if self.zk_client.exists(alert_event_fpath):
            return self.zk_client.get_children(alert_event_fpath)
        else:
            return []

    # 删除告警事件
    def del_alert_event(self, event_name):
        alert_event_path = '/pos/service/exporter/alert/event/%s' % event_name
        if self.zk_client.exists(alert_event_path):
            self.zk_client.delete(alert_event_path)

    def register_datawatch(self, node, znode_monitor):
        self.zk_client.register_datawatch(node, znode_monitor)

    def register_childwatch(self, node, znode_monitor):
        self.zk_client.register_childwatch(node, znode_monitor)


@Singleton
class ConfigCenter(BaseConfigCenter):
    def __init__(self):
        self.zk_client = ZKClient()
        super().__init__(self.zk_client)


class OtherZKClient(object):
    def __init__(self):
        self.zk_client = ''
        self.zk_state = ''
        self.log = logger.Logger()

    def connection_listener(self, state):
        self.zk_state = state

    def connettozkserver(self, zkhosts, connection_listener):
        try:
            retry = KazooRetry(max_tries=-1, backoff=1)  # 退避参数由默认值2改成1，可以减少重连的等待时间
            self.zk_client = KazooClient(
                hosts=zkhosts,
                timeout=4.0,  # 连接超时时间
                connection_retry=retry,  # 连接重试
                logger=logger.Logger()  # 传一个日志对象进行，方便 输出debug日志
            )
            self.zk_client.add_listener(connection_listener)
            self.zk_client.start()

        except Exception as e:
            self.log.error("Cannot connect to Zookeeper: {0}".format(repr(e)))
            self.zk_state = "CLOSED"

    # 关闭zk
    def closetozkserver(self):
        try:
            # 关闭zk客户端
            if self.zk_client != '':
                self.zk_client.stop()
                self.zk_client.close()
                self.zk_client = ''

        except Exception as e:
            self.log.error("closetozkserver: {0}".format(repr(e)))

    # 获取指定ZNode信息
    def get(self, node):
        data, stat = self.zk_client.get(node)
        return data

    # 返回子节点信息
    def get_children(self, node):
        children = self.zk_client.get_children(node)
        return children

    # ZnodeStat of the node if it exists, else None if the node does not exist.
    def exists(self, node):
        znode_status = self.zk_client.exists(node)
        return znode_status

@Singleton
class OtherConfigCenter(BaseConfigCenter):
    def __init__(self):
        self.zk_client = OtherZKClient()
        super().__init__(self.zk_client)
        self.zk_state = ''

    def connection_listener(self, state):
        self.zk_state = state

    def is_zks_connect(self):
        if self.zk_state == "CONNECTED":
            return True
        else:
            return False

    def connettozkserver(self, zkhosts, connection_listener):
        return self.zk_client.connettozkserver(zkhosts, connection_listener)

    def closetozkserver(self):
        return self.zk_client.closetozkserver()