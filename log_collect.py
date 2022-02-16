# _*_ coding:utf-8 _*_
# refactor on:2020/9/21 15:11
# Author   :youweisheng
import copy
import threading

from singleton import Singleton
import logger
import system_api
import config_file
import jsonschema
import re
import os
import json
import subprocess
import time
import zk_client
import exporter
import config
import socket
import signal
import select
import alert_cfg


@Singleton
class LogQueueList(object):
    def __init__(self):
        self.myfifo = []

    def push(self, logpath, logmsg):
        newmsg = {
            "logpath": logpath,
            "logmsg": logmsg
        }
        self.myfifo.append(newmsg)

    def pop(self):
        retmsg = self.myfifo.pop(0)
        if 'logpath' in retmsg and 'logmsg' in retmsg:
            return retmsg['logpath'], retmsg['logmsg']
        else:
            return None, None

    def get(self):
        if len(self.myfifo) > 0 and 'logpath' in self.myfifo[0] and 'logmsg' in self.myfifo[0]:
            return self.myfifo[0]['logpath'], self.myfifo[0]['logmsg']
        else:
            return None, None

    def size(self):
        return len(self.myfifo)


class LogSeek(object):
    def __init__(self):
        self.hcicfg = config.HciConfig()
        if self.hcicfg.is_hci():
            self.log_position = "/usr/lib/python3.6/site-packages/pos-exporter/config/log_position.cfg"
        else:
            self.log_position = "/etc/rcos_private/pos/log_position.cfg"
        self.sys = system_api.SystemApi(5)
        self.log = logger.Logger()
        self.positioncfg = config_file.LogPositionCfg()
        self.wait_log_record_cycle_s = 0.01

    # 获取日志文件的总大小
    def get_log_total(self, logpath):
        try:
            cmd = "wc -l " + logpath
            stdout, stderr = self.sys.process_stdout(cmd)
            return int(stdout.decode('utf-8').split()[0])
        except Exception as e:
            self.log.info("get log<%s> total except: %s", logpath, repr(e))
            return 0

    def get_last_line(self, logfile, line):
        try:
            cmd = "tail -n " + str(line) + " " + logfile
            stdout, stderr = self.sys.process_stdout(cmd)
            return stdout.splitlines()
        except Exception as e:
            self.log.info("get last line except: %s", repr(e))
            return []

    # 该函数的目标是为了获取当前日志在文件的行数
    # 先不考虑日志截断的场景
    def get_lastlog_seek(self, logpath):
        if not os.path.exists(logpath):
            return 0
        # 获取该日志文件最后一条被处理的日志
        lastmsg = self.positioncfg.get_log_position(logpath)
        if lastmsg is None:
            return 0
        # 获取该日志文件的总行数
        totalline = self.get_log_total(logpath)
        if totalline >= 500:
            totalline = 500
        # 如果日志文件不为空
        if totalline > 0:
            # 获取日志文件的最后的日志信息，并与最后一条处理的日志对比，
            # 以判断哪些日志还未处理，从哪行开始采集
            logmsgs = self.get_last_line(logpath, totalline)
            # 从末尾开始匹配日志
            for i in range(len(logmsgs) - 1, 0, -1):
                if logmsgs[i].decode('utf-8') == lastmsg:
                    # 通过匹配到的日志，返回采集点的位置
                    return len(logmsgs) - i - 1
            # 如果未匹配到，一般是因为pos-exporter下线期间，告警日志过多刷没了
            return len(logmsgs)
        # 日志文件为空
        return 0

    def wait_log_record(self, logpath, logmsg, timeout_ms):
        starttime = time.time()
        while True:
            lastmsg = self.positioncfg.get_log_position(logpath)
            if str(lastmsg) == str(logmsg):
                return True
            curtime = time.time()
            if curtime - starttime > timeout_ms or starttime > curtime:
                return False
            time.sleep(self.wait_log_record_cycle_s)

    def save_lastlog(self, logpath, logmsg):
        self.positioncfg.set_log_poistion(logpath, logmsg)


class LogCollect(object):
    def __init__(self):
        self.queue = LogQueueList()
        self.sys = system_api.SystemApi(5)
        self.log = logger.Logger()
        self.logseek = LogSeek()
        self.hcicfg = config.HciConfig()
        if self.hcicfg.is_hci():
            self.sourcefile = copy.deepcopy(alert_cfg.g_hci_alert_file)
        else:
            self.sourcefile = copy.deepcopy(alert_cfg.g_alert_file)
        self.max_log_limit = 5000
        self.reduce_log = 3000
        self.wait_log_record_timeout_s = 5

    def loglistener(self, logpath):
        while True:
            try:
                logline = None
                seek = self.logseek.get_lastlog_seek(logpath)
                cmdline = 'tail -F -n %d %s' % (seek, logpath)
                f = subprocess.Popen(cmdline, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                p = select.poll()
                p.register(f.stdout)
                self.log.info("start listener %s", repr(cmdline))
                while True:
                    # 判断是否有输出
                    if p.poll(1000):
                        for logline in iter(f.stdout.readline, b''):
                            self.log.info("logline: %s", logline)
                            self.queue.push(logpath, logline.decode('utf-8'))
                            # 读取日志时，发现行数超过上限
                            if self.logseek.get_log_total(logpath) > self.max_log_limit:
                                self.log.info("log(%s) out of limit", logpath)
                                break
                    # 起机发现日志超过上限
                    if self.logseek.get_log_total(logpath) > self.max_log_limit:
                        self.log.info("log(%s) out of limit", logpath)
                        break
                # 终止采集
                self.log.info("stop listener %s", logpath)
                p.unregister(f.stdout)
                os.kill(f.pid, signal.SIGKILL)
                # 日志截断，记得关闭pd中的告警日志截断功能
                cmdline = "sed -i '1,%sd' %s" % (str(self.reduce_log), logpath)
                self.sys.process_stdout(cmdline)
                # 这里有一个问题，如果我们在此处就直接再启动采集，那么有可能之前放在队列的日志还未记录，会重复采集
                # 所以要等记录了以后再触发采集
                # 要判断logline是否为空，如果是刚起机，并且没有任何采集，此时logline是空的
                if logline is not None:
                    self.logseek.wait_log_record(logpath, logline.decode('utf-8'), self.wait_log_record_timeout_s)
            except Exception as e:
                self.log.error("log<%s> listen except: %s", logpath, repr(e))  # 输出异常
                time.sleep(1)

    def start(self):
        # 获取要采集的源
        for logpath in self.sourcefile:
            if 'path' not in logpath:
                continue
            threading.Thread(target=self.loglistener, args=(logpath['path'],)).start()


ruleschema = {
    "name": {"type": "string", "maxLength": 64},
    "actionlist": {
        "type": "array",
        "items": {
            "match": {"type": "string", "maxLength": 512},
            "label": {"type": "array"},
            "type": {
                "type": "string",
                "pattern": r"^\bgauge\b$|^\bcounter\b$"
            },
            "action": {
                "type": "string",
                "pattern": r"^\badd\b$|^\bset\b|^\bclr\b$"
            }
        },
        "required": ["match", "label", "type", "action"]
    },
    "required": ["name", "actionlist"]
}


class LogProcess(object):
    def __init__(self):
        self.log = logger.Logger()
        self.queue = LogQueueList()
        self.localcfg = config_file.LocalNodeCfg()
        self.alarmtemp = config_file.AlertTemp()
        self.logseek = LogSeek()
        self.rules = copy.deepcopy(alert_cfg.g_alert_rule)
        self.cfg = zk_client.ConfigCenter()
        self.other_cfg = zk_client.OtherConfigCenter()
        self.sys = system_api.SystemApi(5)
        self.hcicfg = config.HciConfig()
        self.MAX_RULES = 10
        self.zks_port = 9639
        self.alert_gauge_timeout_s = 600
        self.alert_counter_timeout_s = 300
        self.exporter_exit_delay_s = 5
        self.alarm_ip = '0.0.0.0'
        self.alarm_port = 9014
        self.listen_num = 64
        self.recv_max = 8192
        self.socket_timeout = 5
        self.cluster_null_check_cycle_s = 5
        self.extra_label = {
            "server_pos_except": ['ip_addr'],
            "server_pos_version_except": ['ip_addr'],
            "server_papi_except_total": ['ip_addr'],
            "server_zk_except": ['ip_addr'],
            "hard_cache_offline_total": ['ip_addr'],
            "hard_cache_io_timeout_total": ['ip_addr'],
            "hard_snode_io_timeout_total": ['ip_addr'],
            "hard_snet_timeout": ['ip_addr'],
            "hard_snet_except": ['ip_addr'],
            "hard_snet_failed": ['ip_addr'],
            "resource_hugepage_no_enough": ['ip_addr'],
            "pos_subhealth_disk_smart": ['ip_addr'],
            "pos_subhealth_disk_smart_test": ['ip_addr'],
            "pos_subhealth_disk_temperature": ['ip_addr'],
            "pos_subhealth_cache_smart": ['ip_addr'],
            "pos_subhealth_cache_smart_test": ['ip_addr'],
            "pos_subhealth_cache_temperature": ['ip_addr'],
            "pos_subhealth_net_speed": ['ip_addr'],
            "pos_subhealth_net_updown_times": ['ip_addr'],
            "pos_subhealth_net_packet_drops": ['ip_addr'],
            "pos_subhealth_net_packet_errors": ['ip_addr'],
            "pos_subhealth_net_packet_loss_rate": ['ip_addr'],
            "pos_subhealth_net_packet_delay_time": ['ip_addr'],
            "pos_subhealth_net_packet_jitter_time": ['ip_addr'],
            "pos_disk_isolated_status": ['ip_addr'],
            "pos_external_storage_except": ['ip_addr']
        }

    # 对正则表达式的格式做检查
    def regular_check(self, action):
        try:
            pattern = re.compile(action['match'])
            if int(len(pattern.groupindex)) != len(action['label']):
                self.log.error("tag 'match' and tag 'label' no match")
                return False
            for label in action['label']:
                if label not in pattern.groupindex:
                    self.log.error("label not in match")
                    return False
            return True
        except Exception as e:
            self.log.error("Regular expression format exception: %s", repr(e))
            return False

    # 对匹配规则中type与action是否合理做检查
    def metrics_action_check(self, action):
        # 判断为type为gauge时，action是否是set或clr
        if action['type'] == "gauge" and action['action'] == "add":
            self.log.error("The type of the indicator does not match the behavior of the indicator")
            return False
        # 判断为type为counter时，action是否是set或clr
        elif action['type'] == "counter" and action['action'] != "add":
            self.log.error("The type of the indicator does not match the behavior of the indicator")
            return False
        return True

    # 起机后的规则检查
    def rules_check(self):
        try:
            # jsonchema检查
            checker = jsonschema.FormatChecker()
            validator = jsonschema.Draft4Validator(ruleschema, format_checker=checker)
            validator.validate(self.rules, ruleschema)

            # name重名检查
            namelist = []
            for rule in self.rules:
                if rule['name'] in namelist:
                    # 这个地方应该输出报错
                    self.log.error("name check failed")
                    continue
                namelist.append(rule['name'])
                if len(rule['actionlist']) > self.MAX_RULES:
                    self.log.error("actionlist len check failed")
                matchlist = []
                for action in rule['actionlist']:
                    # 判断match重名
                    if action['match'] in matchlist:
                        self.log.error("match check failed")
                        continue
                    # 判断正则表达式的是否合法
                    if not self.regular_check(action):
                        continue
                    # 加入重复判断的列表
                    matchlist.append(action['match'])
                    if not self.metrics_action_check(action):
                        continue
            return True
        except Exception as e:
            self.log.error("rule check except: %s", repr(e))
            return False

    def get_time_stamp(self, logmsg):
        timematch = r"(\d+)-(\d+)-(\d+) (\d+):(\d+):(\d+)"
        pattern = re.compile(timematch)
        matchmsg = pattern.search(logmsg)
        # 如果没有匹配
        if matchmsg is None:
            return int(time.time())
        return int(time.mktime(time.strptime(matchmsg.group(0), "%Y-%m-%d %H:%M:%S")))

    def save_alert_event2zk(self, alert_event):
        try:
            processtime = int(time.time())
            logtime = alert_event['time']
            if alert_event['type'] == "gauge":
                if alert_event['action'] == "set" and processtime - logtime <= self.alert_gauge_timeout_s:
                    self.cfg.create_alert_event(json.dumps(alert_event))
                elif alert_event['action'] == "clr":
                    self.cfg.create_alert_event(json.dumps(alert_event))
            elif alert_event['type'] == "counter" and processtime - logtime <= self.alert_counter_timeout_s:
                self.cfg.create_alert_event(json.dumps(alert_event))
            return True
        except Exception as e:
            self.log.warning("save alert to zookeeper except: %s", repr(e))
            return False

    def save_alert_event(self, name, action, timestamp):
        # 生成指标的命名
        alert_event = {
            'name': name,
            'label': action['label'],
            'type': action['type'],
            'action': action['action'],
            'time': timestamp
        }
        if self.cfg.is_zks_connect():
            # 如果ZK能够连上，更新事件到ZK中
            if not self.save_alert_event2zk(alert_event):
                # 如果保存到ZK失败，则先保存到本地
                self.alarmtemp.insert_alert_tmp(alert_event)
        else:
            self.log.info("zk connect failed")
            self.alarmtemp.insert_alert_tmp(alert_event)

    # 获取额外的标签信息
    def get_extra_label(self, name):
        return self.extra_label.get(name, [])

    # 对匹配规则的处理
    def match_process(self, name, matchmsg, action, timestamp):
        rulename = name
        # 表示有匹配，此时要处理匹配的label
        for cur_label in action['label']:
            # 如果匹配的规则无法识别
            if cur_label not in matchmsg.groupdict():
                self.log.warning("The tag %s could not be found in the parsing information with index name %s",
                                 repr(cur_label), repr(name))
                return False
            name += '&' + cur_label + '=' + str(matchmsg.groupdict()[cur_label])
        # 判断是否需要添加额外的指标
        extra_labels = self.get_extra_label(rulename)
        self.log.info("extra_labels = %s", repr(extra_labels))
        for label in extra_labels:
            if label == 'ip_addr':
                if self.hcicfg.is_hci():
                    ipval = os.getenv('POD_IP', "Omit")
                else:
                    ipval = self.sys.get_local_manage_ip()
                name += '&' + label + '=' + str(ipval)
        # 保存告警事件
        self.log.info("name = %s", name)
        self.log.info("action = %s", repr(action))
        self.log.info("timestamp = %d", timestamp)
        self.save_alert_event(name, action, timestamp)
        return True

    # 获取日志并匹配
    def match(self, message):
        # 遍历所有指标规则
        for rule in self.rules:
            if rule.get('disable', False):
                continue
            # 遍历指标的所有操作
            for action in rule['actionlist']:
                pattern = re.compile(action['match'])
                matchmsg = pattern.search(message)
                # 如果没有匹配
                if matchmsg is None:
                    continue
                self.log.info("match rule: %s", rule['name'])
                timestamp = self.get_time_stamp(message)
                self.log.info("match time: %d", timestamp)
                self.match_process(rule['name'], matchmsg, action, timestamp)

    def get_cluster_svip(self):
        if self.cfg.is_zks_connect():
            return self.cfg.get_cluster_svip()
        else:
            zkhosts = None
            snet_ip_list = self.sys.get_all_snet_ip()
            for snetip in snet_ip_list:
                if zkhosts is None:
                    zkhosts = '%s:%s' % (snetip, self.zks_port)
                else:
                    zkhosts = zkhosts + ',%s:%s' % (snetip, self.zks_port)
            if zkhosts is None:
                return None
            try:
                self.other_cfg.connettozkserver(zkhosts, self.other_cfg.connection_listener)
                if not self.other_cfg.is_zks_connect():
                    raise Exception("cannot connect to zkhost(%s)" % zkhosts)
                svip = self.other_cfg.get_cluster_svip()
                self.other_cfg.closetozkserver()
                return svip
            except Exception as e:
                self.log.error("get cluster svip except : %s", repr(e))
                self.other_cfg.closetozkserver()
                return None

    def alarm_client_send(self, msg):
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socket.setdefaulttimeout(self.socket_timeout)
            # 此时配置中心已经不存在，无法从本节点获取SVIP，SVIP必须从其它节点获取
            svip = self.get_cluster_svip()
            if svip is None:
                return False
            # 连接服务器
            addr = (svip, self.alarm_port)
            self.log.info("svip :%s port:%s", svip, self.alarm_port)
            client.connect(addr)
            client.send(msg.encode('utf-8'))
            recv_data = client.recv(self.recv_max).decode('utf-8')
            client.close()
            if recv_data == "ACK":
                return True
            else:
                return False
        except Exception as e:
            self.log.info("alarm client send except: %s", repr(e))
            if "client" in vars():
                client.close()
            return False

    # 用于监听其它节点发过来的通告，这个只适用于其它节点被删除的场景
    # 报文的接收
    def alarm_listener(self):
        try:
            self.log.info("svip: %s port:%d", self.alarm_ip, self.alarm_port)
            address = (self.alarm_ip, self.alarm_port)
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.bind(address)
            server.listen(self.listen_num)
            while True:
                try:
                    conn, addr = server.accept()
                    data = conn.recv(self.recv_max).decode('utf-8')
                    self.log.info("addr = %s data = %s", repr(addr), repr(data))
                    alert_event = json.loads(data)
                    self.alarmtemp.insert_alert_tmp(alert_event)
                    conn.send("ACK".encode('utf-8'))
                except Exception as e:
                    self.log.info("alarm listener socket process except: %s", repr(e))
                finally:
                    if "conn" in vars():
                        conn.close()
        except Exception as e:
            self.log.error("alarm listener except: %s", repr(e))
            time.sleep(self.exporter_exit_delay_s)
            os._exit(1)

    def start(self):
        # 起机先进行规则检查
        if not self.rules_check():
            self.log.error("Rule check for log matching file failed")
        # 注册告警事件的接收监听
        threading.Thread(target=self.alarm_listener, args=()).start()
        # 轮循日志文件
        while True:
            try:
                alert_tmp_size = self.alarmtemp.get_file_count()
                alert_log_size = self.queue.size()
                if self.cfg.is_zks_connect() and alert_tmp_size > 0:
                    # 判断当前ZK是否连接，如果连接，并且本地缓存中有信息先从本地缓存中取，并保存到ZK中
                    alert_event = self.alarmtemp.get_alert_tmp()
                    if alert_event is not None and self.save_alert_event2zk(alert_event):
                        # 如果保存到ZK成功，再删除本地配置
                        self.alarmtemp.del_alert_tmp()
                elif alert_log_size > 0:
                    # 如果ZK未连接，或者没有本地缓存
                    logpath, logmsg = self.queue.get()
                    self.log.info("alert log <path:%s>, <msg:%s>", logpath, logmsg)
                    self.match(logmsg)
                    self.logseek.save_lastlog(logpath, logmsg)
                    self.queue.pop()
                elif self.localcfg.is_config() == 0 and alert_log_size == 0 and alert_tmp_size > 0:
                    # 如果没有可用节点，则不需要聚合了
                    if self.sys.is_cluster_null():
                        time.sleep(self.cluster_null_check_cycle_s)
                    # 对于节点被删除时，并且队列的日志都保存到本地，并且本地有未处理完的日志
                    alert_event = self.alarmtemp.get_alert_tmp()
                    if alert_event is not None and self.alarm_client_send(json.dumps(alert_event)):
                        # 如果成功发送到服务端，才从本地缓存文件中删除
                        self.alarmtemp.del_alert_tmp()
                else:
                    # 如果没有可以保存的日志
                    time.sleep(0.1)
            except Exception as e:
                self.log.error("The log collection except: %s", repr(e))
                time.sleep(1)


class AlertProcess(object):
    def __init__(self):
        self.alert_event_fpath = "/pos/service/exporter/alert/event"
        self.pos_masterid_path = "/pos/service/P_Deployer_Node/master_election"
        self.pos_cluster_node_fpath = "/pos/cluster/nodes"
        self.pos_cluster_arbitrate_fpath = "/pos/cluster/arbitrate"
        self.alert_timeout_s = 600
        self.alarm_ip = '0.0.0.0'
        self.alarm_port = 9014
        self.listen_num = 64
        self.recv_max = 8192
        self.socket_timeout = 5
        self.log = logger.Logger()
        self.alarmtemp = config_file.AlertTemp()
        self.master_lock = threading.Lock()
        self.event_lock = threading.Lock()
        self.node_lock = threading.Lock()
        self.sys = system_api.SystemApi(5)
        self.cfg = zk_client.ConfigCenter()
        self.exporter = exporter.Exporter()
        self.hcicfg = config.HciConfig()
        self.g_alert_list = []

    def decode_alert_name(self, msg):
        msglist = msg.split('&')
        metrics_name = msglist[0]
        labels = {}
        for label in msglist[1:]:
            labelmsg = label.split('=')
            labels[labelmsg[0]] = labelmsg[1]
        return metrics_name, labels

    # 对于gauge的set与counter事件，超时达到600S以上不再处理
    # 对于gauge的clr事件，超时达到900S以上不再处理
    def alert_event_process_thread(self):
        try:
            # 判断当前节点是否是主节点
            self.event_lock.acquire()
            if not self.sys.is_master_node():
                # 当前不是主节点，不用处理
                self.event_lock.release()
                self.log.info("not master, not process")
                return
            # 由于有可能一些事件已经处理了，为了防止重复处理，需要再获取一次
            childrens = self.cfg.get_alert_event_list()
            childrens.sort()
            # 当前的处理时间，对同一次批次处理的告警事件，处理时间要一致，防止告警未超时，而恢复超时被丢弃
            processtime = int(time.time())
            for child in childrens:
                alert_msg = json.loads(self.cfg.get_alert_event(child))
                self.log.info("alert_event: %s, alert_msg: %s", child, alert_msg)
                metrics_name, labels = self.decode_alert_name(alert_msg['name'])
                logtime = alert_msg['time']
                # 对于gauge的事件，对于set场景，对于超过10分钟未处理的告警，需要丢弃
                if alert_msg['type'] == "gauge" and alert_msg['action'] == "set":
                    if processtime - logtime <= self.alert_timeout_s:
                        self.cfg.save_alert_status(alert_msg['name'])
                        self.g_alert_list = self.cfg.get_alert_status_list()
                        self.exporter.update_alarm(metrics_name, labels, 1)
                    self.cfg.del_alert_event(child)
                # 对于gauge的事件，对于clr场景，只有告警存在才处理，如果连续600S没有相应的告警，则丢弃
                elif alert_msg['type'] == "gauge" and alert_msg['action'] == "clr":
                    if self.cfg.is_alert_status_exist(alert_msg['name']):
                        self.cfg.del_alert_status(alert_msg['name'])
                        self.g_alert_list = self.cfg.get_alert_status_list()
                        self.exporter.update_alarm(metrics_name, labels, 0)
                        self.cfg.del_alert_event(child)
                    else:
                        if processtime - logtime > self.alert_timeout_s:
                            self.log.warning("The current alarm recovery has timed out and has been abandoned")
                            self.cfg.del_alert_event(child)
                        else:
                            # 如果没有告警就收到恢复，那么这个事件先不处理
                            self.log.warning("There is no corresponding alarm for the current "
                                             "recovery event, and it will not be processed temporarily. "
                                             "It will time out after 600 seconds")
                            continue
                # 对于counter事件，超时达到600S以上不再处理
                elif alert_msg['type'] == "counter":
                    if processtime - logtime <= self.alert_timeout_s:
                        self.exporter.update_alarm(metrics_name, labels, 1)
                    self.cfg.del_alert_event(child)
            self.event_lock.release()
        except Exception as e:
            self.log.error("alert_event_process: %s", repr(e))
            self.event_lock.release()

    def alert_event_process(self, childrens):
        threading.Thread(target=self.alert_event_process_thread, args=()).start()

    # 根据VDI环境的需求，要求所有告警metrics都需要提供状态值
    # 由于我们告警是事件型的，并且通过label捆绑资源，
    # 所以在不能感知到具体资源时，无法提供metrics
    # 鉴于R1P5只对外提供pos_ckg_health_status告警，并且上层是以集群方式采集的
    # 所以提供默认的pos_ckg_health_status["poolid"="default"]
    def update_default_alarm(self):
        if self.hcicfg.is_hci():
            return
        self.exporter.update_alarm("pos_ckg_health_status", {'poolid': 'default'}, 0)

    # 用于在主节点切换时，为新的主节点上送信息
    def pos_master_update_alarm(self):
        try:
            self.master_lock.acquire()
            # 启动时要先同步告警状态
            self.g_alert_list = self.cfg.get_alert_status_list()
            self.log.info("alertlist = %s", self.g_alert_list)
            self.update_default_alarm()
            for alert in self.g_alert_list:
                metrics_name, labels = self.decode_alert_name(alert)
                self.exporter.update_alarm(metrics_name, labels, 1)
            self.master_lock.release()
        except Exception as e:
            self.log.error("pos master update alarm: %s", repr(e))
            self.master_lock.release()

    # 主节点切换的处理
    def pos_master_process_thread(self):
        try:
            # 判断是否是主节点，如果不是主节点，不用处理
            if not self.sys.is_master_node():
                self.log.info("remove exporter alarm")
                self.remove_exporter_alarm()
                return
            # 如果是主节点，删除不存在的资源的告警（删除节点触发的主节点切换）
            self.remove_unuse_alarm()
            # 更新主节点的告警
            self.pos_master_update_alarm()
        except Exception as e:
            self.log.error("alert_event_process: %s", repr(e))

    # 监听到主节点切换
    def pos_master_process(self, master_data, master_stat):
        threading.Thread(target=self.pos_master_process_thread, args=()).start()

    # 删除无用的告警
    def remove_unuse_alarm(self):
        try:
            self.node_lock.acquire()
            # 获取IP列表
            iplist = []
            nodelist = self.cfg.get_nodes_uuid()
            for nodeid in nodelist:
                ip = self.sys.get_manage_ip(str(nodeid))
                if ip is not None:
                    iplist.append(ip)
            # 获取所有告警列表
            alertlist = self.cfg.get_alert_status_list()
            for alert in alertlist:
                metrics_name, labels = self.decode_alert_name(alert)
                if 'ip_addr' in labels and labels['ip_addr'] not in iplist:
                    # 该告警指标不存在于当前节点，则删除该指标
                    self.exporter.remove_alarm(metrics_name, labels)
                    self.cfg.del_alert_status(alert)
            self.node_lock.release()
        except Exception as e:
            self.log.error("remove unuse alarm except: %s", repr(e))
            self.node_lock.release()

    # 监听到节点变化，可能是添加节点也可能是删除节点
    def pos_node_process_thread(self):
        try:
            # 非主节点不处理
            if not self.sys.is_master_node():
                self.log.info("not master, not process")
                return
            self.remove_unuse_alarm()
        except Exception as e:
            self.log.error("pos_node_process: %s", repr(e))

    def pos_node_process(self, childrens):
        threading.Thread(target=self.pos_node_process_thread, args=()).start()

    def remove_exporter_alarm(self):
        # 获取所有告警列表
        for alert in self.g_alert_list:
            metrics_name, labels = self.decode_alert_name(alert)
            # 该告警指标不存在于当前节点，则删除该指标
            self.log.info("remove metrics: %s, label: %s", metrics_name, repr(labels))
            self.exporter.remove_alarm(metrics_name, labels)

    # 这个流程只有在主节点启动，所以需要判断当前是否是主节点
    def start(self):
        try:
            self.cfg.alert_event_init()
            # 注册主节点切换的事件
            self.cfg.register_datawatch(self.pos_masterid_path, self.pos_master_process)
            # 注册告警事件的监听
            self.cfg.register_childwatch(self.alert_event_fpath, self.alert_event_process)
            # 注册节点增加与减少的监听
            self.cfg.register_childwatch(self.pos_cluster_node_fpath, self.pos_node_process)
            self.cfg.register_childwatch(self.pos_cluster_arbitrate_fpath, self.pos_node_process)
        except Exception as e:
            self.log.info("start alert event process except: %s", repr(e))


class AlarmModule(object):
    def __init__(self):
        self.logcol = LogCollect()
        self.logpro = LogProcess()

    def start(self):
        threading.Thread(target=self.logcol.start, args=()).start()
        threading.Thread(target=self.logpro.start, args=()).start()
