
g_alert_file = [
    {
        "path": "/var/log/rcos/pos/pos_alert.log"
    },
    {
        "path": "/var/log/rcos/pdeployer/alert.log"
    },
    {
        "path": "/var/log/rcos/psubhealth/subhealth_alert.log"
    },
    {
        "path": "/var/log/rcos/premotebackup/remotebackup_alert.log"
    }
]

g_hci_alert_file = [
    {
        "path": "/var/log/rcos/pos/pos_alert.log"
    },
    {
        "path": "/var/log/rcos/premotebackup/remotebackup_alert.log"
    }
]

g_alert_rule = [
    # 服务告警 #
    # RCOS-POS服务异常退出
    {
        "name": "server_pos_except",
        "actionlist": [
            {
                "match": "pos service offline",
                "label": [],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": "pos service online",
                "label": [],
                "type": "gauge",
                "action": "clr"
            },
            {
                "match": "Initialization complete",
                "label": [],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # RCOS-PAPI模块异常
    {
        "name": "server_papi_except_total",
        "actionlist": [{
            "match": "papi server except",
            "label": [],
            "type": "counter",
            "action": "add"
        }]
    },
    # Zookeeper服务异常
    {
        "name": "server_zk_except",
        "actionlist": [
            {
                "match": r"current zookeeper offline: \((?P<cluster_id>[-0-9a-zA-Z]+)\)",
                "label": ["cluster_id"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"current zookeeper online: \((?P<cluster_id>[-0-9a-zA-Z]+)\)",
                "label": ["cluster_id"],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # POS版本过低
    {
        "name": "server_pos_version_except",
        "actionlist": [
            {
                "match": "pos version does not meet (.*) conditions",
                "label": [],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": "pos service online",
                "label": [],
                "type": "gauge",
                "action": "clr"
            },
            {
                "match": "Initialization complete",
                "label": [],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # 硬件告警 #
    # 缓存盘异常
    {
        "name": "hard_cache_offline_total",
        "actionlist": [{
            "match": "sn<([-0-9a-zA-Z]+)> (.*) : The exception occurred",
            "label": [],
            "type": "counter",
            "action": "add"
        }]
    },
    # 缓存盘IO延时超过阈值
    {
        "name": "hard_cache_io_timeout_total",
        "actionlist": [{
            "match": r"sn<([-0-9a-zA-Z]+)> (.*) : IO latency exceeded the threshold, size (\d+) bytes, "
                     r"interval (\d+) ns",
            "label": [],
            "type": "counter",
            "action": "add"
        }]
    },
    # 容量盘IO延时超过阈值
    {
        "name": "hard_snode_io_timeout_total",
        "actionlist": [{
            "match": r"sbio (0[xX][0-9a-fA-F]+) exec by disk\[([-0-9a-zA-Z]+)\]\[(\d+)\] timeout, cost (\d+)\(ms\), "
                     r"threshold (\d+)\(ms\)",
            "label": [],
            "type": "counter",
            "action": "add"
        }]
    },
    # pos存储网传输超时 & pos存储网传输异常 & pos存储网连接失败
    {
        "name": "hard_snet_timeout",
        "actionlist": [
            {
                "match": r"pmsg timeout\(session_id=(\d+);local_node_id=(\d+);remote_node_id=(\d+)\)",
                "label": [],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": "pmsg session connect success",
                "label": [],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    {
        "name": "hard_snet_except",
        "actionlist": [
            {
                "match": r"pmsg client disconnect starting\(session_id=(\d+);"
                         r"local_node_id=(\d+);remote_node_id=(\d+)\)",
                "label": [],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": "pmsg session connect success",
                "label": [],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    {
        "name": "hard_snet_failed",
        "actionlist": [
            {
                "match": r"pmsg qpair connect failed\(session_id=(\d+);local_node_id=(\d+);remote_node_id=(\d+)\)",
                "label": [],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": "pmsg session connect success",
                "label": [],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # 软件告警 #
    # 存储池元数据读写失败
    {
        "name": "soft_pool_rw_failed",
        "disable": True,
        "actionlist": [
            {
                "match": r"pool\[(?P<poolid>\d+)\] metadata inaccessible",
                "label": ["poolid"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"pool\[(?P<poolid>\d+)\] metadata accessible",
                "label": ["poolid"],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # 存储池数据副本不是以节点隔离
    {
        "name": "pos_ckg_health_status",
        "actionlist": [
            {
                "match": r"pool\[(?P<poolid>\d+)\]\[.*\] check all ckg health status",
                "label": ["poolid"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"pool\[(?P<poolid>\d+)\]\[.*\] all ckg healthy",
                "label": ["poolid"],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # VDISK进入不可服务状态
    {
        "name": "soft_vdisk_unsevice",
        "disable": True,
        "actionlist": [
            {
                "match": r"vdisk \[(?P<poolid>\d+)\]\[(?P<vdiskid>\d+)\] set unserviceable",
                "label": ["poolid", "vdiskid"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"vdisk \[(?P<poolid>\d+)\]\[(?P<vdiskid>\d+)\] set serviceable",
                "label": ["poolid", "vdiskid"],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # VDISK数据校验失败
    {
        "name": "soft_vdisk_datacheck_failed",
        "disable": True,
        "actionlist": [
            {
                "match": r"vdisk \[(?P<poolid>\d+)\]\[(?P<vdiskid>\d+)\] retry read data crc checksum verify failed",
                "label": ["poolid", "vdiskid"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"vdisk \[(?P<poolid>\d+)\]\[(?P<vdiskid>\d+)\] retry read data succeed",
                "label": ["poolid", "vdiskid"],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # VDISK数据日志节点的RCOS-POS未启动
    {
        "name": "soft_vdisk_datalog_pos_unservice",
        "disable": True,
        "actionlist": [
            {
                "match": r"Can't open journal of vdisk\[(?P<poolid>\d+)\]\[(?P<vdiskid>\d+)\], for mirror node offline",
                "label": ["poolid", "vdiskid"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"Open journal of vdisk\[(?P<poolid>\d+)\]\[(?P<vdiskid>\d+)\] successfully",
                "label": ["poolid", "vdiskid"],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # VDISK数据日志不完整
    {
        "name": "soft_vdisk_datalog_imperfect",
        "actionlist": [
            {
                "match": r"P-Journal init failed, ret (-?\d+)",
                "label": [],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": "P-Journal init success",
                "label": [],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # VDISK数据日志回放时校验失败
    {
        "name": "soft_vdisk_datalog_check_failed",
        "disable": True,
        "actionlist": [
            {
                "match": r"Journal of vdisk\[(?P<poolid>\d+)\]\[(?P<vdiskid>\d+)\] replay failed",
                "label": ["poolid", "vdiskid"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"Recover journal of vdisk\[(?P<poolid>\d+)\]\[(?P<vdiskid>\d+)\] success",
                "label": ["poolid", "vdiskid"],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # SCSI发生IO超时
    {
        "name": "soft_scsi_much_to_latency_total",
        "disable": True,
        "actionlist": [{
            "match": r"lun \[(?P<poolid>\d+)\]\[(?P<vdiskid>\d+)\]\[(?P<volumeid>\d+)\]\[(?P<snapshotid>\d+)\] io "
                     r"size:(.*) io type:(\d+) timeout, cost (\d+)\(ms\), threshold 100\(ms\)",
            "label": ["poolid", "vdiskid", "volumeid", "snapshotid"],
            "type": "counter",
            "action": "add"
        }]
    },
    {
        "name": "soft_scsi_io_timeout_total",
        "disable": True,
        "actionlist": [{
            "match": r"lun \[(?P<poolid>\d+)\]\[(?P<vdiskid>\d+)\]\[(?P<volumeid>\d+)\]\[(?P<snapshotid>\d+)\] io "
                     r"size:(.*) io type:(\d+) timeout, cost (\d+)\(ms\), threshold 30\(s\)",
            "label": ["poolid", "vdiskid", "volumeid", "snapshotid"],
            "type": "counter",
            "action": "add"
        }]
    },
    # SCSI发生IO错误
    {
        "name": "soft_scsi_io_failed_total",
        "disable": True,
        "actionlist": [{
            "match": r"lun \[(?P<poolid>\d+)\]\[(?P<vdiskid>\d+)\]\[(?P<volumeid>\d+)\]\[(?P<snapshotid>\d+)\] io "
                     r"error, ltask_sense:(0[xX][0-9a-fA-F]+), io type:(\d+)",
            "label": ["poolid", "vdiskid", "volumeid", "snapshotid"],
            "type": "counter",
            "action": "add"
        }]
    },
    # 资源告警 #
    # VDISK可写空间不足
    {
        "name": "resource_vdisk_capacity_unenough",
        "disable": True,
        "actionlist": [
            {
                "match": r"vdisk \[(?P<poolid>\d+)\]\[(?P<vdiskid>\d+)\] dsa space is not enough",
                "label": ["poolid", "vdiskid"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"vdisk \[(?P<poolid>\d+)\]\[(?P<vdiskid>\d+)\] space recover",
                "label": ["poolid", "vdiskid"],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # Zookeeper工作目录可用空间不足
    {
        "name": "resource_zookeeper_unenough_total",
        "actionlist": [{
            "match": r"zookeeper data size \((\d+)\)MB exceeds the threshold",
            "label": [],
            "type": "counter",
            "action": "add"
        }]
    },
    # Zookeeper内存空间不足
    {
        "name": "resource_zookeeper_mem_unenough_total",
        "actionlist": [{
            "match": r"zookeeper memory \((\d+)\)MB exceeds the threshold",
            "label": [],
            "type": "counter",
            "action": "add"
        }]
    },
    # 卷和快照数量过多
    {
        "name": "resource_volume_or_snapshot_unenough",
        "disable": True,
        "actionlist": [
            {
                "match": r"Snapshot count of volume \[(?P<poolid>\d+)\]\[(?P<vdiskid>\d+)\]"
                         r"\[(?P<volumeid>\d+)\] reaches max\((\d+)\)",
                "label": ["poolid", "vdiskid", "volumeid"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"Snapshot count of volume \[(?P<poolid>\d+)\]\[(?P<vdiskid>\d+)\]\[(?P<volumeid>\d+)\] is (\d+)",
                "label": ["poolid", "vdiskid", "volumeid"],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # 卷残留
    {
        "name": "resource_volume_residual",
        "disable": True,
        "actionlist": [
            {
                "match": r"delete volume \[(?P<poolid>\d+)\]\[(?P<vdiskid>\d+)\]\[(?P<volumeid>\d+)\] "
                         r"failed, ret (-?\d+)",
                "label": ["poolid", "vdiskid", "volumeid"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"delete volume \[(?P<poolid>\d+)\]\[(?P<vdiskid>\d+)\]\[(?P<volumeid>\d+)\] success",
                "label": ["poolid", "vdiskid", "volumeid"],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # 快照残留
    {
        "name": "resource_snapshot_residual",
        "disable": True,
        "actionlist": [
            {
                "match": r"delete snapshot \[(?P<poolid>\d+)\]\[(?P<vdiskid>\d+)\]\[(?P<volumeid>\d+)\]"
                         r"\[(?P<snapshotid>\d+)\] failed, ret (-?\d+)",
                "label": ["poolid", "vdiskid", "volumeid", "snapshotid"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"delete snapshot \[(?P<poolid>\d+)\]\[(?P<vdiskid>\d+)\]\[(?P<volumeid>\d+)\]"
                         r"\[(?P<snapshotid>\d+)\] success",
                "label": ["poolid", "vdiskid", "volumeid", "snapshotid"],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # 大页内存不足
    {
        "name": "resource_volume_or_snapshot_residual",
        "actionlist": [
            {
                "match": r"EAL: Not enough memory available",
                "label": [],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"Start init uns",
                "label": [],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # 亚健康告警 #
    # 磁盘亚健康-smart属性异常
    {
        "name": "pos_subhealth_disk_smart",
        "actionlist": [
            {
                "match": r"node (?P<node>\d+) device (?P<disk_sn>.*) is RISKY, \[disk\]-\[smart\]",
                "label": ["node", "disk_sn"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<disk_sn>.*) is FAULTY, \[disk\]-\[smart\]",
                "label": ["node", "disk_sn"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<disk_sn>.*) is HEALTHY, \[disk\]-\[smart\]",
                "label": ["node", "disk_sn"],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # 磁盘亚健康-smart测试异常
    {
        "name": "pos_subhealth_disk_smart_test",
        "actionlist": [
            {
                "match": r"node (?P<node>\d+) device (?P<disk_sn>.*) is RISKY, \[disk\]-\[smart-test\]",
                "label": ["node", "disk_sn"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<disk_sn>.*) is FAULTY, \[disk\]-\[smart-test\]",
                "label": ["node", "disk_sn"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<disk_sn>.*) is HEALTHY, \[disk\]-\[smart-test\]",
                "label": ["node", "disk_sn"],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # 磁盘亚健康-磁盘温度异常
    {
        "name": "pos_subhealth_disk_temperature",
        "actionlist": [
            {
                "match": r"node (?P<node>\d+) device (?P<disk_sn>.*) is RISKY, \[disk\]-\[temperature\]",
                "label": ["node", "disk_sn"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<disk_sn>.*) is FAULTY, \[disk\]-\[temperature\]",
                "label": ["node", "disk_sn"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<disk_sn>.*) is HEALTHY, \[disk\]-\[temperature\]",
                "label": ["node", "disk_sn"],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # 缓存盘亚健康-smart属性异常
    {
        "name": "pos_subhealth_cache_smart",
        "actionlist": [
            {
                "match": r"node (?P<node>\d+) device (?P<disk_sn>.*) is RISKY, \[cache\]-\[smart\]",
                "label": ["node", "disk_sn"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<disk_sn>.*) is FAULTY, \[cache\]-\[smart\]",
                "label": ["node", "disk_sn"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<disk_sn>.*) is HEALTHY, \[cache\]-\[smart\]",
                "label": ["node", "disk_sn"],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # 缓存盘亚健康-smart测试异常
    {
        "name": "pos_subhealth_cache_smart_test",
        "actionlist": [
            {
                "match": r"node (?P<node>\d+) device (?P<disk_sn>.*) is RISKY, \[cache\]-\[smart-test\]",
                "label": ["node", "disk_sn"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<disk_sn>.*) is FAULTY, \[cache\]-\[smart-test\]",
                "label": ["node", "disk_sn"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<disk_sn>.*) is HEALTHY, \[cache\]-\[smart-test\]",
                "label": ["node", "disk_sn"],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # 缓存盘亚健康-磁盘温度异常
    {
        "name": "pos_subhealth_cache_temperature",
        "actionlist": [
            {
                "match": r"node (?P<node>\d+) device (?P<disk_sn>.*) is RISKY, \[cache\]-\[temperature\]",
                "label": ["node", "disk_sn"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<disk_sn>.*) is FAULTY, \[cache\]-\[temperature\]",
                "label": ["node", "disk_sn"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<disk_sn>.*) is HEALTHY, \[cache\]-\[temperature\]",
                "label": ["node", "disk_sn"],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # 磁盘隔离
    {
        "name": "pos_disk_isolated_status",
        "actionlist": [
            {
                "match": r"node (?P<node>\d+) device (?P<disk_sn>.*) is ISOLATED",
                "label": ["node", "disk_sn"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<disk_sn>.*) is NOT-ISOLATED",
                "label": ["node", "disk_sn"],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # 网卡端口亚健康-速度异常
    {
        "name": "pos_subhealth_net_speed",
        "actionlist": [
            {
                "match": r"node (?P<node>\d+) device (?P<device>.*) is RISKY, \[netcard\]-\[speed\]",
                "label": ["node", "device"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<device>.*) is FAULTY, \[netcard\]-\[speed\]",
                "label": ["node", "device"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<device>.*) is HEALTHY, \[netcard\]-\[speed\]",
                "label": ["node", "device"],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # 网卡端口亚健康-闪断次数超过上限
    {
        "name": "pos_subhealth_net_updown_times",
        "actionlist": [
            {
                "match": r"node (?P<node>\d+) device (?P<device>.*) is RISKY, \[netcard\]-\[updown-times\]",
                "label": ["node", "device"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<device>.*) is FAULTY, \[netcard\]-\[updown-times\]",
                "label": ["node", "device"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<device>.*) is HEALTHY, \[netcard\]-\[updown-times\]",
                "label": ["node", "device"],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # 网卡端口亚健康-丢包发生
    {
        "name": "pos_subhealth_net_packet_drops",
        "actionlist": [
            {
                "match": r"node (?P<node>\d+) device (?P<device>.*) is RISKY, \[netcard\]-\[packet-drops\]",
                "label": ["node", "device"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<device>.*) is FAULTY, \[netcard\]-\[packet-drops\]",
                "label": ["node", "device"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<device>.*) is HEALTHY, \[netcard\]-\[packet-drops\]",
                "label": ["node", "device"],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # 网卡端口亚健康-错包发生
    {
        "name": "pos_subhealth_net_packet_errors",
        "actionlist": [
            {
                "match": r"node (?P<node>\d+) device (?P<device>.*) is RISKY, \[netcard\]-\[packet-errors\]",
                "label": ["node", "device"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<device>.*) is FAULTY, \[netcard\]-\[packet-errors\]",
                "label": ["node", "device"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<device>.*) is HEALTHY, \[netcard\]-\[packet-errors\]",
                "label": ["node", "device"],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # 集群网络亚健康-丢包率超过上限
    {
        "name": "pos_subhealth_net_packet_loss_rate",
        "actionlist": [
            {
                "match": r"node (?P<node>\d+) device (?P<device>.*) is RISKY, "
                         r"\[cluster-network\]-\[packet-loss-rate\]",
                "label": ["node", "device"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<device>.*) is FAULTY, "
                         r"\[cluster-network\]-\[packet-loss-rate\]",
                "label": ["node", "device"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<device>.*) is HEALTHY, "
                         r"\[cluster-network\]-\[packet-loss-rate\]",
                "label": ["node", "device"],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # 集群网络亚健康-延迟时间超过上限
    {
        "name": "pos_subhealth_net_packet_delay_time",
        "actionlist": [
            {
                "match": r"node (?P<node>\d+) device (?P<device>.*) is RISKY, "
                         r"\[cluster-network\]-\[packet-delay-time\]",
                "label": ["node", "device"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<device>.*) is FAULTY, "
                         r"\[cluster-network\]-\[packet-delay-time\]",
                "label": ["node", "device"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<device>.*) is HEALTHY, "
                         r"\[cluster-network\]-\[packet-delay-time\]",
                "label": ["node", "device"],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # 集群网络亚健康-抖动时间超过上限
    {
        "name": "pos_subhealth_net_packet_jitter_time",
        "actionlist": [
            {
                "match": r"node (?P<node>\d+) device (?P<device>.*) is RISKY, "
                         r"\[cluster-network\]-\[packet-jitter-time\]",
                "label": ["node", "device"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<device>.*) is FAULTY, "
                         r"\[cluster-network\]-\[packet-jitter-time\]",
                "label": ["node", "device"],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"node (?P<node>\d+) device (?P<device>.*) is HEALTHY, "
                         r"\[cluster-network\]-\[packet-jitter-time\]",
                "label": ["node", "device"],
                "type": "gauge",
                "action": "clr"
            }
        ]
    },
    # 远程备份
    # 备份/恢复过程外置存储异常
    {
        "name": "pos_external_storage_except",
        "actionlist": [
            {
                "match": r"nodeid (?P<node>\d+), backup write/read external storage failed",
                "label": [],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"nodeid (?P<node>\d+), backup write external storage no space",
                "label": [],
                "type": "gauge",
                "action": "set"
            },
            {
                "match": r"nodeid (?P<node>\d+), backup write/read external storage normal",
                "label": [],
                "type": "gauge",
                "action": "clr"
            }
        ]
    }
]
