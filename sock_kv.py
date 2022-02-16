"""
Author: your name
Date: 2021-08-30 11:16:45
LastEditTime: 2021-08-30 16:53:59
LastEditors: Please set LastEditors
Description: In User Settings Edit
FilePath: \\pos-exporter\\server\\sock_kv.py
"""
from singleton import Singleton
import re


@Singleton
class SocketKVpair(object):
    DATA_SYNC_CHNN = "__SOCKET_KV_PAIR__"

    def __init__(self, my_id):
        super().__init__()
        self._data = {}
        self.my_id = my_id
        import system_api
        self.sys = system_api.SystemApi(5)
        self.sys.register_mcast_listener(self.DATA_SYNC_CHNN, self._node_data_listener)

    def __setitem__(self, key, val):
        self.sys.send_mcast_msg(self.DATA_SYNC_CHNN, key, val)

    def __getitem__(self, key):
        return self._data.get(key, None)

    def _node_data_listener(self, ip, key, data):
        self._data[key] = data
        self._nouse(ip)

    def _nouse(self, x):
        _, x = x, x

    def _get_key(self, base_key, my_id):
        if my_id is None:
            my_id = self.my_id
        return f"__{base_key}_{my_id}__"

    def _get_my_id_list_by_base_key(self, base_key):
        ret = []
        reg = re.compile(f"__{base_key}_(\\w+)__")
        for k in self._data:
            partten = reg.fullmatch(k)
            if partten:
                ret.append(partten.groups()[0])
        return ret

    def _node_monitor_key(self, my_id=None):
        return self._get_key("node_monitor_key", my_id)

    def _cluster_monitor_key(self, my_id=None):
        return self._get_key("cluster_monitor_key", my_id)

    def _monitor_history_key(self, my_id=None):
        return self._get_key("monitor_history_key", my_id)

    def cfg_save_node_monitor(self, value):
        self[self._node_monitor_key()] = value

    def cfg_get_node_monitor(self, myid=None):
        return self[self._node_monitor_key(myid)]

    def cfg_get_monitor_nodes(self):
        return self._get_my_id_list_by_base_key("node_monitor_key")

    def cfg_save_cluster_monitor(self, value):
        self[self._cluster_monitor_key()] = value

    def cfg_get_cluster_monitor(self):
        return self[self._cluster_monitor_key()]
