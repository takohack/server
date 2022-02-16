# _*_ coding:utf-8 _*_
# refactor on:2021/9/14 11:16
# Author   :lizidong

import logger
from pos_rpc import JSONRPCClient


class RemoteBackupSubState:
    __slots__ = ('TotalIoNum', 'LastIoNum', 'LastElapse', 'LastSize')

    def __init__(self, **kwargs) -> None:
        self.TotalIoNum = kwargs['TotalIoNum']
        self.LastIoNum = kwargs['LastIoNum']
        self.LastSize = kwargs['LastSize']
        last_elapse = kwargs['LastElapse']
        if isinstance(last_elapse, str):
            last_elapse = self._str_to_sec(last_elapse)
        self.LastElapse = last_elapse

    @staticmethod
    def _str_to_sec(time_str):
        num_elapse = 0
        time_str = time_str.replace('ms','a')
        hour_pos = time_str.find('h')
        if hour_pos != -1:
            num_elapse += 3600 * float(time_str[0:hour_pos])
            time_str = time_str[hour_pos + 1:]
        min_pos = time_str.find('m')
        if min_pos != -1:
            num_elapse += 60 * float(time_str[0:min_pos])
            time_str = time_str[min_pos + 1:]
        sec_pos = time_str.find('s')
        ms_pos = time_str.find('a')
        if sec_pos != -1:
            num_elapse += float(time_str[0:sec_pos])
            if ms_pos != -1:
                num_elapse += float(time_str[sec_pos + 1:ms_pos]) * 0.001
        elif time_str:
            time_str = time_str.strip()
            if time_str:
                if ms_pos == -1:
                    num_elapse += float(time_str)
                else:
                    num_elapse += float(time_str[0:ms_pos]) * 0.001

        return num_elapse


class RemoteBackupState:
    __slots__ = ('ProcessID', 'Restore', 'Backup')

    def __init__(self, **kwargs) -> None:
        self.ProcessID = kwargs['ProcessID']
        stats = kwargs['GroupStats']
        self.Restore = RemoteBackupSubState(**stats['Restore'])
        self.Backup = RemoteBackupSubState(**stats['Backup'])

    @classmethod
    def default(cls):
        return RemoteBackupState(**{
            'ProcessID': 0,
            'GroupStats': {
                'Restore': {
                    'TotalIoNum': 0,
                    'LastIoNum': 0,
                    'LastElapse': 0,
                    'LastSize': 0,
                },
                'Backup': {
                    'TotalIoNum': 0,
                    'LastIoNum': 0,
                    'LastElapse': 0,
                    'LastSize': 0,
                }
            }
        })


class RemoteBackupJSONRPCClient(object):
    SERVER_PORT = 9015

    @classmethod
    def get_backup_state(cls, addr) -> RemoteBackupState:
        response = None
        try:
            rpc = JSONRPCClient(addr, cls.SERVER_PORT)
            response = rpc.call('GetBackupStats', params={"GroupName": "backup/restore"})
            return RemoteBackupState(**response)
        except Exception as e:
            logger.Logger().error(f"GetBackupStats: {repr(e)}:{response}")
            return None
