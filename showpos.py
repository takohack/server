from multiprocessing import pool

import zk_client
import config_file
import subprocess
from kazoo.client import KazooState
import re
import json


cfg = zk_client.ConfigCenter()
localcfg = config_file.LocalNodeCfg()

def connection_listener(state):
    if state == KazooState.LOST:
        print(state)
    elif state == KazooState.SUSPENDED:
        print(state)
    else:
        pass

if not cfg.is_zks_connect():
    localhost_ip = "127.0.0.1"
    zk_server = localhost_ip + ":" + localcfg.get_client_port()
    cfg.connettozkserver(zk_server,connection_listener)
def print_header():
    print("Myid" +"---"+ "Nodeid"+ "---"+ "Mnetip" + "---" + "Snetip" + "---" + "Status" + "---" + "Arbitrate")

def get_papi_status(nodes_info):
    command = "docker service ps papiserver | grep Running"
    papi_info = {}
    papi_info['node_myid'] = 'N/A'
    papi_info['running_state'] = 'N/A'
    result = subprocess.run(command,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout.decode('utf-8')
    result_list = result.split()
    if 'Running' in result_list:
        print('Running')
        node_id = result_list[3]
        for node in nodes_info:
            if node.nodeid == node_id:
                papi_info['node_myid'] = node.myid
        current_state = "Running("+ result_list[5]+" "+result_list[6]+" "+result_list[7]+")"
        papi_info['running_state'] = current_state
        return papi_info
    else:
        return papi_info

def get_zookeeper_leader(nodes_info):

    for node in nodes_info:
        node_snetvip = node.snetip
        command = "echo stat|nc "+node_snetvip+" 9639| grep Mode:"
        result = subprocess.check_output(command,shell=True).decode('utf-8')
        if result.find('Mode: leader') != -1:
            return node.myid
    return 'N/A'    

def checkprameter(resource,resourceid):
    rules = {
        "pool": "\d+$",
        "vdisk": "\d+-\d+$",
        "volume": "\d+-\d+-\d+$",
        "snapshot": "\d+-\d+-\d+-\d+$"
    }
    resource_type = ['pool','vdisk','volume','snapshot']
    if not resource in resource_type:
        return 'The resource parameter is illegal. The resource value is not within the range of pool|vdisk|volume|snapshot'
    if resource == 'pool':
        if re.match(rules["pool"],resourceid):
            match_result = re.match(rules["pool"],resourceid)
            pool_query = [match_result.group(0)]
            return pool_query
        else:
            return "The resourceid parameter does not match the resource type(pool). should be {pool}"
    elif resource == 'vdisk':
        if re.match(rules["vdisk"],resourceid):
            match_result = re.match(rules["vdisk"],resourceid)
            vdisk_query = match_result.group(0).split('-')
            return vdisk_query
        else:
            return "The resourceid parameter does not match the resource type(vdisk).should be  {poolid}-{vdiskid}"
    elif resource == 'volume':
        if re.match(rules["volume"],resourceid):
            match_result = re.match(rules["volume"],resourceid)
            volume_query = match_result.group(0).split('-')
            return volume_query
        else:
            return "The resourceid parameter does not match the resource type(volume).should be  {poolid}-{vdiskid}-{volumeid}"
    else:
        if re.match(rules["snapshot"],resourceid):
            match_result = re.match(rules["snapshot"],resourceid)
            snapshot_query = match_result.group(0).split('-')
            return snapshot_query
        else:
            return "The resourceid parameter does not match the resource type(snapshot).should be  {poolid}-{vdiskid}-{volumeid}-{snapshotid}"

def print_json(data):
    json_object = json.loads(data)
    json_formatted_str = json.dumps(json_object, indent=2)
    print(json_formatted_str)

def get_resources_byid(resource,resourceid):
    query_info = checkprameter(resource,resourceid)
    if isinstance(query_info,str): #
        print(query_info)
        return -1
    else:
        if resource == 'pool':
            pool_info = cfg.get_pool_byid(query_info)
            print("Pool(%s)Config View" % (query_info[0]))
            print_json(pool_info['config_view'])
            print("Pool(%s)State View" % (query_info[0]))
            print_json(pool_info['state_view'])
        elif resource == 'vdisk':
            vdisk_info = cfg.get_vdisk_byid(query_info)
            print("Pool(%s) Vdisk(%s)Config View" % (query_info[0],query_info[1]))
            print_json(vdisk_info['config_view'])
            print("Pool(%s) Vdisk(%s)State View" % (query_info[0],query_info[1]))
            print_json(vdisk_info['state_view'])
        elif resource == 'volume': #测试0-7-0 0-8-0
            volume_info = cfg.get_volume_byid(query_info)
            print("Pool(%s) Vdisk(%s) Volume(%s)Config View" % (query_info[0],query_info[1],query_info[2]))
            print_json(volume_info['config_view'])
            print("Pool(%s) Vdisk(%s) Volume(%s)State View" % (query_info[0],query_info[1],query_info[2]))
            print_json(volume_info['state_view'])
        else: #测试0-7-0-1 0-8-0-1
            snapshot_info = cfg.get_snapshot_byid(query_info)
            print("Pool(%s) Vdisk(%s) Volume(%s) Snapshot(%s)Config View" % (query_info[0],query_info[1],query_info[2],query_info[3]))
            print_json(snapshot_info['config_view'])
            print("Pool(%s) Vdisk(%s) Volume(%s) Snapshot(%s)State View" % (query_info[0],query_info[1],query_info[2],query_info[3]))
            print_json(snapshot_info['state_view'])

def get_resources_byname(resource,resourcename,parentid=None):
    resource_type = ['pool','vdisk','volume','snapshot']
    if not resource in resource_type:
        return 'The resource parameter is illegal. The resource value is not within the range of pool|vdisk|volume|snapshot'
    if resource == 'pool': #parentid should be None
        if parentid != None:
            print("The resourceid parameter does not match the resource type(Pool).Pool should not hava parentid")
            return -1
        pool_info = cfg.get_pool_byname(resourcename)
        resource_id = pool_info["resource_id"]
        print("Pool(%s)Config View" % (resource_id[0]))
        print_json(pool_info['config_view'])
        print("Pool(%s)State View" % (resource_id[0]))
        print_json(pool_info['state_view'])
    if resource == 'vdisk':  #pareneid should be pooid or none 可能会有不同vdisk的重名
        pass

def show_allnode():
    print("Cluster ID:" + cfg.get_cluster_id())
    print_header()
    nodes_info = cfg.get_nodes_info()
    for node in nodes_info:
        print(node)
    pools_info = cfg.get_pools_info()
    print("Pool Count:" + str(len(pools_info)))
    print(pools_info)
    print("Vdisk Count:" + str(cfg.get_vdisk_num()))
    print("Iscsi Target Count:" + str(cfg.get_iscsi_num()))
    print("Zookeeper Leader:" + get_zookeeper_leader(nodes_info))
    print("Pos Master:" + str(cfg.get_pos_masterid()))
    print("PD Master:" + str(cfg.get_pd_master()))
    print("SnetVIP:" + str(cfg.get_cluster_svip()))
    print("MnetVIP:" + str(cfg.get_cluster_mvip()))
    papi_status = get_papi_status(nodes_info)
    print("PAPI Running Node: " + papi_status['node_myid'])
    print("PAPI Running State: " + papi_status['running_state'])
    

#show_allnode()
# nodes_info = cfg.get_nodes_info()
# get_papi_status(nodes_info)
#get_resources_byid('vdisk',"0-7")
get_resources_byname('pool',"pool0")


