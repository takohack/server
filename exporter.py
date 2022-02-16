# _*_ coding:utf-8 _*_
# refactor on:2020/9/21 15:11
# Author   :youweisheng

from prometheus_client import Counter, Gauge
from enum import Enum
import logger
from singleton import Singleton


class Dimension(Enum):
    CLUSTER = "Cluster"
    NODE = "Node"
    POOL = "Pool"
    IPADDR = "IpAddr"
    DISK = "Disk"


class MetricNode(Enum):
    ReadIO = 'ReadIO'
    WriteIO = 'WriteIO'
    ReadByte = 'ReadByte'
    WriteByte = 'WriteByte'
    ReadLatency = 'ReadLatency'
    WriteLatency = 'WriteLatency'
    DataL1Hits = 'DataL1Hits'
    DataL2Hits = 'DataL2Hits'
    DataMisses = 'DataMisses'
    UsedCap = 'UsedCap'
    MaxUsedCap = 'MaxUsedCap'
    TotalCap = 'TotalCap'
    BadBlock = 'BadBlock'
    UnrepairBlock = 'UnrepairBlock'
    ZKMem = 'ZKMem'  # 当前Zookeeper的内存占用
    ZKDir = 'ZKDir'  # 当前Zookeeper快照与日志对存储空间的占用
    ZKMaxMem = 'ZKMaxMem'  # 当前Zookeeper内存的上限
    ZKMaxDir = 'ZKMaxDir'  # 当前Zookeeper快照与日志大小的上限
    BackupTotalIoNum = 'BTotalIoNum'
    BackupLastIoNum = 'BLastIoNum'
    BackupLastElapse = 'BLastElapse'
    BackupLastSize = 'BLastSize'
    RestoreTotalIoNum = 'RTotalIoNum'
    RestoreLastIoNum = 'RLastIoNum'
    RestoreLastElapse = 'RLastElapse'
    RestoreLastSize = 'RLastSize'

    @classmethod
    def from_str(cls, metric_str):
        for v in cls:
            if metric_str == v.value or metric_str == v.name:
                return v
        return None


@Singleton
class Exporter(object):
    def __init__(self):
        # 当前这个default标签只提供给cluster_id集群，当前集群是不用label的
        self.DEFAULT_LABEL = "default"
        self.log = logger.Logger()
        # 集群指标
        self.pos_cluster_reads_completed = Counter("pos_cluster_reads_completed", "", ['cluster_id'])
        self.pos_cluster_writes_completed = Counter("pos_cluster_writes_completed", "", ['cluster_id'])
        self.pos_cluster_read_bytes = Counter("pos_cluster_read_bytes", "", ['cluster_id'])
        self.pos_cluster_written_bytes = Counter("pos_cluster_written_bytes", "", ['cluster_id'])
        self.pos_cluster_reads_time_seconds = Counter("pos_cluster_reads_time_seconds", "", ['cluster_id'])
        self.pos_cluster_writes_time_seconds = Counter("pos_cluster_writes_time_seconds", "", ['cluster_id'])
        self.pos_cluster_cache_l1_hits = Counter("pos_cluster_cache_l1_hits", "", ['cluster_id'])
        self.pos_cluster_cache_l2_hits = Counter("pos_cluster_cache_l2_hits", "", ['cluster_id'])
        self.pos_cluster_cache_data_misses = Counter("pos_cluster_cache_data_misses", "", ['cluster_id'])
        self.pos_cluster_capacity_used = Gauge("pos_cluster_capacity_used", "", ['cluster_id'])
        self.pos_cluster_capacity_total = Gauge("pos_cluster_capacity_total", "", ['cluster_id'])
        self.pos_cluster_capacity_max_used = Gauge("pos_cluster_capacity_max_used", "", ['cluster_id'])
        # 磁盘指标
        self.pos_disk_bad_block = Gauge("pos_disk_bad_block", "", ['disk_sn', 'pool_id'])
        self.pos_disk_unrepair_block = Gauge("pos_disk_unrepair_block", "", ['disk_sn', 'pool_id'])
        # 存储池指标
        self.pos_pool_reads_completed = Counter("pos_pool_reads_completed", "", ['pool_id'])
        self.pos_pool_writes_completed = Counter("pos_pool_writes_completed", "", ['pool_id'])
        self.pos_pool_read_bytes = Counter("pos_pool_read_bytes", "", ['pool_id'])
        self.pos_pool_written_bytes = Counter("pos_pool_written_bytes", "", ['pool_id'])
        self.pos_pool_reads_time_seconds = Counter("pos_pool_reads_time_seconds", "", ['pool_id'])
        self.pos_pool_writes_time_seconds = Counter("pos_pool_writes_time_seconds", "", ['pool_id'])
        self.pos_pool_cache_l1_hits = Counter("pos_pool_cache_l1_hits", "", ['pool_id'])
        self.pos_pool_cache_l2_hits = Counter("pos_pool_cache_l2_hits", "", ['pool_id'])
        self.pos_pool_cache_data_misses = Counter("pos_pool_cache_data_misses", "", ['pool_id'])
        self.pos_pool_capacity_used = Gauge("pos_pool_capacity_used", "", ['pool_id'])
        self.pos_pool_capacity_total = Gauge("pos_pool_capacity_total", "", ['pool_id'])
        # 节点指标
        self.pos_node_reads_completed = Counter("pos_node_reads_completed", "", ['host_id'])
        self.pos_node_writes_completed = Counter("pos_node_writes_completed", "", ['host_id'])
        self.pos_node_read_bytes = Counter("pos_node_read_bytes", "", ['host_id'])
        self.pos_node_written_bytes = Counter("pos_node_written_bytes", "", ['host_id'])
        self.pos_node_reads_time_seconds = Counter("pos_node_reads_time_seconds", "", ['host_id'])
        self.pos_node_writes_time_seconds = Counter("pos_node_writes_time_seconds", "", ['host_id'])
        self.pos_node_cache_l1_hits = Counter("pos_node_cache_l1_hits", "", ['host_id'])
        self.pos_node_cache_l2_hits = Counter("pos_node_cache_l2_hits", "", ['host_id'])
        self.pos_node_cache_data_misses = Counter("pos_node_cache_data_misses", "", ['host_id'])
        # 节点中的zookeeper指标
        self.zookeeper_memory_use = Gauge("zookeeper_memory_use", "", ['ip_addr'])
        self.zookeeper_datadir_use = Gauge("zookeeper_datadir_use", "", ['ip_addr'])
        self.zookeeper_memory_total = Gauge("zookeeper_memory_total", "", ['ip_addr'])
        self.zookeeper_datadir_total = Gauge("zookeeper_datadir_total", "", ['ip_addr'])

        # 告警指标-服务告警
        self.server_pos_except = Gauge("server_pos_except", "", ['ip_addr'])
        self.server_papi_except_total = Counter("server_papi_except", "", ['ip_addr'])
        self.server_zk_except = Gauge("server_zk_except", "", ['ip_addr'])
        self.server_pos_version_except = Gauge("server_pos_version_except", "", ['ip_addr'])
        # 告警指标-硬件告警
        self.hard_cache_offline_total = Counter("hard_cache_offline", "", ['ip_addr'])
        self.hard_cache_io_timeout_total = Counter("hard_cache_io_timeout", "", ['ip_addr'])
        self.hard_snode_io_timeout_total = Counter("hard_snode_io_timeout", "", ['ip_addr'])
        self.hard_snet_timeout = Gauge("hard_snet_timeout", "", ['ip_addr'])
        self.hard_snet_except = Gauge("hard_snet_except", "", ['ip_addr'])
        self.hard_snet_failed = Gauge("hard_snet_failed", "", ['ip_addr'])
        # 告警指标-软件告警
        self.pos_ckg_health_status = Gauge("pos_ckg_health_status", "", ['poolid'])
        self.soft_pool_rw_failed = Gauge("soft_pool_rw_failed", "", ['poolid'])
        self.soft_vdisk_unsevice = Gauge("soft_vdisk_unsevice", "", ['poolid', 'vdiskid'])
        self.soft_vdisk_datacheck_failed = Gauge("soft_vdisk_datacheck_failed", "", ['poolid', 'vdiskid'])
        self.soft_vdisk_datalog_pos_unservice = Gauge("soft_vdisk_datalog_pos_unservice", "", ['poolid', 'vdiskid'])
        self.soft_vdisk_datalog_imperfect = Gauge("soft_vdisk_datalog_imperfect", "", ['cluster_id'])
        self.soft_vdisk_datalog_check_failed = Gauge("soft_vdisk_datalog_check_failed", "", ['poolid', 'vdiskid'])
        self.soft_scsi_much_to_latency_total = Counter("soft_scsi_much_to_latency", "",
                                                       ['poolid', 'vdiskid', 'volumeid', 'snapshotid'])
        self.soft_scsi_io_timeout_total = Counter("soft_scsi_io_timeout", "", ['poolid', 'vdiskid', 'volumeid', 'snapshotid'])
        self.soft_scsi_io_failed_total = Counter("soft_scsi_io_failed", "", ['poolid', 'vdiskid', 'volumeid', 'snapshotid'])
        # 告警指标-资源告警
        self.resource_vdisk_capacity_unenough = Gauge("resource_vdisk_capacity_unenough", "", ['poolid', 'vdiskid'])
        self.resource_volume_or_snapshot_unenough = Gauge("resource_volume_or_snapshot_unenough", "",
                                                          ['poolid', 'vdiskid', 'volumeid'])
        self.resource_volume_or_snapshot_residual = Gauge("resource_volume_or_snapshot_residual", "",
                                                          ['poolid', 'vdiskid', 'volumeid', 'snapshotid'])
        self.resource_hugepage_no_enough = Gauge("resource_hugepage_no_enough", "", ['ip_addr'])
        # 告警指标-亚健康告警
        self.pos_disk_isolated_status = Gauge("pos_disk_isolated_status", "", ['node', 'disk_sn', 'ip_addr'])
        self.pos_subhealth_disk_smart = Gauge("pos_subhealth_disk_smart", "", ['node', 'disk_sn', 'ip_addr'])
        self.pos_subhealth_disk_smart_test = Gauge("pos_subhealth_disk_smart_test", "", ['node', 'disk_sn', 'ip_addr'])
        self.pos_subhealth_disk_temperature = Gauge("pos_subhealth_disk_temperature", "", ['node', 'disk_sn', 'ip_addr'])
        self.pos_subhealth_cache_smart = Gauge("pos_subhealth_cache_smart", "", ['node', 'disk_sn', 'ip_addr'])
        self.pos_subhealth_cache_smart_test = Gauge("pos_subhealth_cache_smart_test", "", ['node', 'disk_sn', 'ip_addr'])
        self.pos_subhealth_cache_temperature = Gauge("pos_subhealth_cache_temperature", "", ['node', 'disk_sn', 'ip_addr'])
        self.pos_subhealth_net_speed = Gauge("pos_subhealth_net_speed", "", ['node', 'device', 'ip_addr'])
        self.pos_subhealth_net_updown_times = Gauge("pos_subhealth_net_updown_times", "", ['node', 'device', 'ip_addr'])
        self.pos_subhealth_net_packet_drops = Gauge("pos_subhealth_net_packet_drops", "", ['node', 'device', 'ip_addr'])
        self.pos_subhealth_net_packet_errors = Gauge("pos_subhealth_net_packet_errors", "", ['node', 'device', 'ip_addr'])
        self.pos_subhealth_net_packet_loss_rate = Gauge("pos_subhealth_net_packet_loss_rate", "", ['node', 'device', 'ip_addr'])
        self.pos_subhealth_net_packet_delay_time = Gauge("pos_subhealth_net_packet_delay_time", "", ['node', 'device', 'ip_addr'])
        self.pos_subhealth_net_packet_jitter_time = Gauge("pos_subhealth_net_packet_jitter_time", "", ['node', 'device', 'ip_addr'])
        # 节点中的remotebackup指标
        self.bakup_total_io_num = Counter("bakup_io_num", "", ['ip_addr'])
        self.bakup_last_io_num = Gauge("bakup_last_io_num", "", ['ip_addr'])
        self.bakup_last_elapse = Gauge("bakup_last_elapse", "", ['ip_addr'])
        self.bakup_last_size = Gauge("bakup_last_size", "", ['ip_addr'])
        self.restore_total_io_num = Counter("restore_io_num", "", ['ip_addr'])
        self.restore_last_io_num = Gauge("restore_last_io_num", "", ['ip_addr'])
        self.restore_last_elapse = Gauge("restore_last_elapse", "", ['ip_addr'])
        self.restore_last_size = Gauge("restore_last_size", "", ['ip_addr'])
        self.pos_external_storage_except = Gauge("pos_external_storage_except", "", ['ip_addr'])

    # 在类里定义一个装饰器
    def exception_catch(func):  # func接收body
        def ware(self, *args, **kwargs):  # self,接收body里的self,也就是类实例
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                self.log.info("%s exception: %s", func.__qualname__, repr(e))

        return ware

    @exception_catch
    def remove_backup_total_io_num_metric(self, metric_dim, metric_param):
        if metric_dim == Dimension.NODE.value:
            self.bakup_total_io_num.remove(metric_param)
        else:
            self.log.info("remove_backup_total_io_num_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def update_backup_total_io_num_metric(self, metric_dim, metric_param, value):
        if metric_dim == Dimension.NODE.value:
            self.bakup_total_io_num.labels(metric_param).inc(value)
        else:
            self.log.info("update_backup_total_io_num_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def remove_backup_last_io_num_metric(self, metric_dim, metric_param):
        if metric_dim == Dimension.NODE.value:
            self.bakup_last_io_num.remove(metric_param)
        else:
            self.log.info("remove_backup_last_io_num_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def update_backup_last_io_num_metric(self, metric_dim, metric_param, value):
        if metric_dim == Dimension.NODE.value:
            self.bakup_last_io_num.labels(metric_param).set(value)
        else:
            self.log.info("update_backup_last_io_num_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def remove_backup_last_elapse_metric(self, metric_dim, metric_param):
        if metric_dim == Dimension.NODE.value:
            self.bakup_last_elapse.remove(metric_param)
        else:
            self.log.info("remove_backup_last_elapse_num_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def update_backup_last_elapse_metric(self, metric_dim, metric_param, value):
        if metric_dim == Dimension.NODE.value:
            self.bakup_last_elapse.labels(metric_param).set(value)
        else:
            self.log.info("update_backup_last_elapse_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def remove_backup_last_size_metric(self, metric_dim, metric_param):
        if metric_dim == Dimension.NODE.value:
            self.bakup_last_size.remove(metric_param)
        else:
            self.log.info("remove_backup_last_size_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def update_backup_last_size_num_metric(self, metric_dim, metric_param, value):
        if metric_dim == Dimension.NODE.value:
            self.bakup_last_size.labels(metric_param).set(value)
        else:
            self.log.info("update_backup_last_size_num_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def remove_restore_total_io_num_metric(self, metric_dim, metric_param):
        if metric_dim == Dimension.NODE.value:
            self.restore_total_io_num.remove(metric_param)
        else:
            self.log.info("remove_restore_total_io_num_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def update_restore_total_io_num_metric(self, metric_dim, metric_param, value):
        if metric_dim == Dimension.NODE.value:
            self.restore_total_io_num.labels(metric_param).inc(value)
        else:
            self.log.info("update_restore_total_io_num_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def remove_restore_last_io_num_metric(self, metric_dim, metric_param):
        if metric_dim == Dimension.NODE.value:
            self.restore_last_io_num.remove(metric_param)
        else:
            self.log.info("remove_restore_last_io_num_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def update_restore_last_io_num_metric(self, metric_dim, metric_param, value):
        if metric_dim == Dimension.NODE.value:
            self.restore_last_io_num.labels(metric_param).set(value)
        else:
            self.log.info("update_restore_last_io_num_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def remove_restore_last_elapse_metric(self, metric_dim, metric_param):
        if metric_dim == Dimension.NODE.value:
            self.restore_last_elapse.remove(metric_param)
        else:
            self.log.info("remove_restore_last_elapse_num_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def update_restore_last_elapse_metric(self, metric_dim, metric_param, value):
        if metric_dim == Dimension.NODE.value:
            self.restore_last_elapse.labels(metric_param).set(value)
        else:
            self.log.info("update_restore_last_elapse_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def remove_restore_last_size_metric(self, metric_dim, metric_param):
        if metric_dim == Dimension.NODE.value:
            self.restore_last_size.remove(metric_param)
        else:
            self.log.info("remove_restore_last_size_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def update_restore_last_size_num_metric(self, metric_dim, metric_param, value):
        if metric_dim == Dimension.NODE.value:
            self.restore_last_size.labels(metric_param).set(value)
        else:
            self.log.info("update_restore_last_size_num_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def update_readio_metric(self, metric_dim, metric_param, value):
        if metric_dim == Dimension.CLUSTER.value:
            self.pos_cluster_reads_completed.labels(self.DEFAULT_LABEL).inc(value)
        elif metric_dim == Dimension.POOL.value:
            self.pos_pool_reads_completed.labels(metric_param).inc(value)
        elif metric_dim == Dimension.NODE.value:
            self.pos_node_reads_completed.labels(metric_param).inc(value)
        else:
            self.log.info("update_readio_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def update_writeio_metric(self, metric_dim, metric_param, value):
        if metric_dim == Dimension.CLUSTER.value:
            self.pos_cluster_writes_completed.labels(self.DEFAULT_LABEL).inc(value)
        elif metric_dim == Dimension.POOL.value:
            self.pos_pool_writes_completed.labels(metric_param).inc(value)
        elif metric_dim == Dimension.NODE.value:
            self.pos_node_writes_completed.labels(metric_param).inc(value)
        else:
            self.log.info("update_writeio_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def update_readbytes_metric(self, metric_dim, metric_param, value):
        if metric_dim == Dimension.CLUSTER.value:
            self.pos_cluster_read_bytes.labels(self.DEFAULT_LABEL).inc(value)
        elif metric_dim == Dimension.POOL.value:
            self.pos_pool_read_bytes.labels(metric_param).inc(value)
        elif metric_dim == Dimension.NODE.value:
            self.pos_node_read_bytes.labels(metric_param).inc(value)
        else:
            self.log.info("update_readbytes_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def update_writebytes_metric(self, metric_dim, metric_param, value):
        if metric_dim == Dimension.CLUSTER.value:
            self.pos_cluster_written_bytes.labels(self.DEFAULT_LABEL).inc(value)
        elif metric_dim == Dimension.POOL.value:
            self.pos_pool_written_bytes.labels(metric_param).inc(value)
        elif metric_dim == Dimension.NODE.value:
            self.pos_node_written_bytes.labels(metric_param).inc(value)
        else:
            self.log.info("update_writebytes_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def update_read_latency_metric(self, metric_dim, metric_param, value):
        if metric_dim == Dimension.CLUSTER.value:
            self.pos_cluster_reads_time_seconds.labels(self.DEFAULT_LABEL).inc(value)
        elif metric_dim == Dimension.POOL.value:
            self.pos_pool_reads_time_seconds.labels(metric_param).inc(value)
        elif metric_dim == Dimension.NODE.value:
            self.pos_node_reads_time_seconds.labels(metric_param).inc(value)
        else:
            self.log.info("update_read_latency_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def update_write_latency_metric(self, metric_dim, metric_param, value):
        if metric_dim == Dimension.CLUSTER.value:
            self.pos_cluster_writes_time_seconds.labels(self.DEFAULT_LABEL).inc(value)
        elif metric_dim == Dimension.POOL.value:
            self.pos_pool_writes_time_seconds.labels(metric_param).inc(value)
        elif metric_dim == Dimension.NODE.value:
            self.pos_node_writes_time_seconds.labels(metric_param).inc(value)
        else:
            self.log.info("update_write_latency_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def update_datal1_hit_metric(self, metric_dim, metric_param, value):
        if metric_dim == Dimension.CLUSTER.value:
            self.pos_cluster_cache_l1_hits.labels(self.DEFAULT_LABEL).inc(value)
        elif metric_dim == Dimension.POOL.value:
            self.pos_pool_cache_l1_hits.labels(metric_param).inc(value)
        elif metric_dim == Dimension.NODE.value:
            self.pos_node_cache_l1_hits.labels(metric_param).inc(value)
        else:
            self.log.info("update_datal1_hit_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def update_datal2_hit_metric(self, metric_dim, metric_param, value):
        if metric_dim == Dimension.CLUSTER.value:
            self.pos_cluster_cache_l2_hits.labels(self.DEFAULT_LABEL).inc(value)
        elif metric_dim == Dimension.POOL.value:
            self.pos_pool_cache_l2_hits.labels(metric_param).inc(value)
        elif metric_dim == Dimension.NODE.value:
            self.pos_node_cache_l2_hits.labels(metric_param).inc(value)
        else:
            self.log.info("update_datal2_hit_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def update_data_miss_metric(self, metric_dim, metric_param, value):
        if metric_dim == Dimension.CLUSTER.value:
            self.pos_cluster_cache_data_misses.labels(self.DEFAULT_LABEL).inc(value)
        elif metric_dim == Dimension.POOL.value:
            self.pos_pool_cache_data_misses.labels(metric_param).inc(value)
        elif metric_dim == Dimension.NODE.value:
            self.pos_node_cache_data_misses.labels(metric_param).inc(value)
        else:
            self.log.info("update_data_miss_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def update_capacity_used_metric(self, metric_dim, metric_param, value):
        if metric_dim == Dimension.CLUSTER.value:
            self.pos_cluster_capacity_used.labels(self.DEFAULT_LABEL).set(value)
        elif metric_dim == Dimension.POOL.value:
            self.pos_pool_capacity_used.labels(metric_param).set(value)
        else:
            self.log.info("update_capacity_used_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def update_capacity_max_used_metric(self, metric_dim, metric_param, value):
        if metric_dim == Dimension.CLUSTER.value:
            self.pos_cluster_capacity_max_used.labels(self.DEFAULT_LABEL).set(value)
        else:
            self.log.info("update_capacity_max_used_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def update_capacity_total_metric(self, metric_dim, metric_param, value):
        if metric_dim == Dimension.CLUSTER.value:
            self.pos_cluster_capacity_total.labels(self.DEFAULT_LABEL).set(value)
        elif metric_dim == Dimension.POOL.value:
            self.pos_pool_capacity_total.labels(metric_param).set(value)
        else:
            self.log.info("update_capacity_total_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def update_disk_bad_block_metric(self, disk_sn, pool_id, value):
        self.log.info("update pos_disk_bad_block [disksn: %s, poolid:%d]", disk_sn, pool_id)
        self.pos_disk_bad_block.labels(disk_sn, pool_id).set(value)

    @exception_catch
    def update_disk_unrepair_block_metric(self, disk_sn, pool_id, value):
        self.pos_disk_unrepair_block.labels(disk_sn, pool_id).set(value)

    @exception_catch
    def update_zookeeper_memory_use_metric(self, metric_dim, metric_param, value):
        if metric_dim == Dimension.IPADDR.value:
            self.zookeeper_memory_use.labels(metric_param).set(value)
        else:
            self.log.info("update_zookeeper_memory_use_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def update_zookeeper_datadir_use_metric(self, metric_dim, metric_param, value):
        if metric_dim == Dimension.IPADDR.value:
            self.zookeeper_datadir_use.labels(metric_param).set(value)
        else:
            self.log.info("update_zookeeper_datadir_use_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def update_zookeeper_memory_total_metric(self, metric_dim, metric_param, value):
        if metric_dim == Dimension.IPADDR.value:
            self.zookeeper_memory_total.labels(metric_param).set(value)
        else:
            self.log.info("update_zookeeper_memory_total_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def update_zookeeper_datadir_total_metric(self, metric_dim, metric_param, value):
        if metric_dim == Dimension.IPADDR.value:
            self.zookeeper_datadir_total.labels(metric_param).set(value)
        else:
            self.log.info("update_zookeeper_datadir_total_metric parameter<metric_dim> error: %s", repr(metric_dim))

    @exception_catch
    def remove_readio_metric(self, metric_dim, metric_param):
        if metric_dim == Dimension.CLUSTER.value:
            self.pos_cluster_reads_completed.remove(self.DEFAULT_LABEL)
        elif metric_dim == Dimension.POOL.value:
            self.pos_pool_reads_completed.remove(metric_param)
        elif metric_dim == Dimension.NODE.value:
            self.pos_node_reads_completed.remove(metric_param)

    @exception_catch
    def remove_writeio_metric(self, metric_dim, metric_param):
        if metric_dim == Dimension.CLUSTER.value:
            self.pos_cluster_writes_completed.remove(self.DEFAULT_LABEL)
        elif metric_dim == Dimension.POOL.value:
            self.pos_pool_writes_completed.remove(metric_param)
        elif metric_dim == Dimension.NODE.value:
            self.pos_node_writes_completed.remove(metric_param)

    @exception_catch
    def remove_readbytes_metric(self, metric_dim, metric_param):
        if metric_dim == Dimension.CLUSTER.value:
            self.pos_cluster_read_bytes.remove(self.DEFAULT_LABEL)
        elif metric_dim == Dimension.POOL.value:
            self.pos_pool_read_bytes.remove(metric_param)
        elif metric_dim == Dimension.NODE.value:
            self.pos_node_read_bytes.remove(metric_param)

    @exception_catch
    def remove_writebytes_metric(self, metric_dim, metric_param):
        if metric_dim == Dimension.CLUSTER.value:
            self.pos_cluster_written_bytes.remove(self.DEFAULT_LABEL)
        if metric_dim == Dimension.POOL.value:
            self.pos_pool_written_bytes.remove(metric_param)
        elif metric_dim == Dimension.NODE.value:
            self.pos_node_written_bytes.remove(metric_param)

    @exception_catch
    def remove_read_latency_metric(self, metric_dim, metric_param):
        if metric_dim == Dimension.CLUSTER.value:
            self.pos_cluster_reads_time_seconds.remove(self.DEFAULT_LABEL)
        elif metric_dim == Dimension.POOL.value:
            self.pos_pool_reads_time_seconds.remove(metric_param)
        elif metric_dim == Dimension.NODE.value:
            self.pos_node_reads_time_seconds.remove(metric_param)

    @exception_catch
    def remove_write_latency_metric(self, metric_dim, metric_param):
        if metric_dim == Dimension.CLUSTER.value:
            self.pos_cluster_writes_time_seconds.remove(self.DEFAULT_LABEL)
        elif metric_dim == Dimension.POOL.value:
            self.pos_pool_writes_time_seconds.remove(metric_param)
        elif metric_dim == Dimension.NODE.value:
            self.pos_node_writes_time_seconds.remove(metric_param)

    @exception_catch
    def remove_datal1_hit_metric(self, metric_dim, metric_param):
        if metric_dim == Dimension.CLUSTER.value:
            self.pos_cluster_cache_l1_hits.remove(self.DEFAULT_LABEL)
        elif metric_dim == Dimension.POOL.value:
            self.pos_pool_cache_l1_hits.remove(metric_param)
        elif metric_dim == Dimension.NODE.value:
            self.pos_node_cache_l1_hits.remove(metric_param)

    @exception_catch
    def remove_datal2_hit_metric(self, metric_dim, metric_param):
        if metric_dim == Dimension.CLUSTER.value:
            self.pos_cluster_cache_l2_hits.remove(self.DEFAULT_LABEL)
        elif metric_dim == Dimension.POOL.value:
            self.pos_pool_cache_l2_hits.remove(metric_param)
        elif metric_dim == Dimension.NODE.value:
            self.pos_node_cache_l2_hits.remove(metric_param)

    @exception_catch
    def remove_data_miss_metric(self, metric_dim, metric_param):
        if metric_dim == Dimension.CLUSTER.value:
            self.pos_cluster_cache_data_misses.remove(self.DEFAULT_LABEL)
        elif metric_dim == Dimension.POOL.value:
            self.pos_pool_cache_data_misses.remove(metric_param)
        elif metric_dim == Dimension.NODE.value:
            self.pos_node_cache_data_misses.remove(metric_param)

    @exception_catch
    def remove_capacity_used_metric(self, metric_dim, metric_param):
        if metric_dim == Dimension.CLUSTER.value:
            self.pos_cluster_capacity_used.remove(self.DEFAULT_LABEL)
        elif metric_dim == Dimension.POOL.value:
            self.pos_pool_capacity_used.remove(metric_param)

    @exception_catch
    def remove_capacity_max_used_metric(self, metric_dim, metric_param):
        if metric_dim == Dimension.CLUSTER.value:
            self.pos_cluster_capacity_max_used.remove(self.DEFAULT_LABEL)

    @exception_catch
    def remove_capacity_total_metric(self, metric_dim, metric_param):
        if metric_dim == Dimension.CLUSTER.value:
            self.pos_cluster_capacity_total.remove(self.DEFAULT_LABEL)
        elif metric_dim == Dimension.POOL.value:
            self.pos_pool_capacity_total.remove(metric_param)

    @exception_catch
    def remove_disk_bad_block_metric(self, disk_sn, pool_id):
        self.pos_disk_bad_block.remove(disk_sn, pool_id)

    @exception_catch
    def remove_disk_unrepair_block_metric(self, disk_sn, pool_id):
        self.pos_disk_unrepair_block.remove(disk_sn, pool_id)

    @exception_catch
    def remove_zookeeper_memory_use_metric(self, metric_dim, metric_param):
        if metric_dim == Dimension.IPADDR.value:
            self.zookeeper_memory_use.remove(metric_param)

    @exception_catch
    def remove_zookeeper_datadir_use_metric(self, metric_dim, metric_param):
        if metric_dim == Dimension.IPADDR.value:
            self.zookeeper_datadir_use.remove(metric_param)

    @exception_catch
    def remove_zookeeper_memory_total_metric(self, metric_dim, metric_param):
        if metric_dim == Dimension.IPADDR.value:
            self.zookeeper_memory_total.remove(metric_param)

    @exception_catch
    def remove_zookeeper_datadir_total_metric(self, metric_dim, metric_param):
        if metric_dim == Dimension.IPADDR.value:
            self.zookeeper_datadir_total.remove(metric_param)

    def update_metric(self, metric_name, metric_dim, metric_param, value):
        if metric_name == MetricNode.ReadIO.value:
            self.update_readio_metric(metric_dim, metric_param, value)
        elif metric_name == MetricNode.WriteIO.value:
            self.update_writeio_metric(metric_dim, metric_param, value)
        elif metric_name == MetricNode.ReadByte.value:
            self.update_readbytes_metric(metric_dim, metric_param, value)
        elif metric_name == MetricNode.WriteByte.value:
            self.update_writebytes_metric(metric_dim, metric_param, value)
        elif metric_name == MetricNode.ReadLatency.value:
            self.update_read_latency_metric(metric_dim, metric_param, value)
        elif metric_name == MetricNode.WriteLatency.value:
            self.update_write_latency_metric(metric_dim, metric_param, value)
        elif metric_name == MetricNode.DataL1Hits.value:
            self.update_datal1_hit_metric(metric_dim, metric_param, value)
        elif metric_name == MetricNode.DataL2Hits.value:
            self.update_datal2_hit_metric(metric_dim, metric_param, value)
        elif metric_name == MetricNode.DataMisses.value:
            self.update_data_miss_metric(metric_dim, metric_param, value)
        elif metric_name == MetricNode.UsedCap.value:
            self.update_capacity_used_metric(metric_dim, metric_param, value)
        elif metric_name == MetricNode.MaxUsedCap.value:
            self.update_capacity_max_used_metric(metric_dim, metric_param, value)
        elif metric_name == MetricNode.TotalCap.value:
            self.update_capacity_total_metric(metric_dim, metric_param, value)
        elif metric_name == MetricNode.BadBlock.value:
            self.update_disk_bad_block_metric(metric_dim, metric_param, value)
        elif metric_name == MetricNode.UnrepairBlock.value:
            self.update_disk_unrepair_block_metric(metric_dim, metric_param, value)
        elif metric_name == MetricNode.ZKMem.value:
            self.update_zookeeper_memory_use_metric(metric_dim, metric_param, value)
        elif metric_name == MetricNode.ZKDir.value:
            self.update_zookeeper_datadir_use_metric(metric_dim, metric_param, value)
        elif metric_name == MetricNode.ZKMaxMem.value:
            self.update_zookeeper_memory_total_metric(metric_dim, metric_param, value)
        elif metric_name == MetricNode.ZKMaxDir.value:
            self.update_zookeeper_datadir_total_metric(metric_dim, metric_param, value)
        elif metric_name == MetricNode.BackupTotalIoNum.value:
            self.update_backup_total_io_num_metric(metric_dim, metric_param, value)
        elif metric_name == MetricNode.BackupLastIoNum.value:
            self.update_backup_last_io_num_metric(metric_dim, metric_param, value)
        elif metric_name == MetricNode.BackupLastElapse.value:
            self.update_backup_last_elapse_metric(metric_dim, metric_param, value)
        elif metric_name == MetricNode.BackupLastSize.value:
            self.update_backup_last_size_num_metric(metric_dim, metric_param, value)
        elif metric_name == MetricNode.RestoreTotalIoNum.value:
            self.update_restore_total_io_num_metric(metric_dim, metric_param, value)
        elif metric_name == MetricNode.RestoreLastIoNum.value:
            self.update_restore_last_io_num_metric(metric_dim, metric_param, value)
        elif metric_name == MetricNode.RestoreLastElapse.value:
            self.update_restore_last_elapse_metric(metric_dim, metric_param, value)
        elif metric_name == MetricNode.RestoreLastSize.value:
            self.update_restore_last_size_num_metric(metric_dim, metric_param, value)
        else:
            self.log.info("metric name<metric_dim> error: %s", repr(metric_name))

    def remove_metric(self, metric_dim, metric_param):
        self.remove_readio_metric(metric_dim, metric_param)
        self.remove_writeio_metric(metric_dim, metric_param)
        self.remove_readbytes_metric(metric_dim, metric_param)
        self.remove_writebytes_metric(metric_dim, metric_param)
        self.remove_read_latency_metric(metric_dim, metric_param)
        self.remove_write_latency_metric(metric_dim, metric_param)
        self.remove_datal1_hit_metric(metric_dim, metric_param)
        self.remove_datal2_hit_metric(metric_dim, metric_param)
        self.remove_data_miss_metric(metric_dim, metric_param)
        self.remove_capacity_used_metric(metric_dim, metric_param)
        self.remove_capacity_max_used_metric(metric_dim, metric_param)
        self.remove_capacity_total_metric(metric_dim, metric_param)
        self.remove_backup_total_io_num_metric(metric_dim, metric_param)
        self.remove_backup_last_size_metric(metric_dim, metric_param)
        self.remove_backup_last_elapse_metric(metric_dim, metric_param)
        self.remove_backup_last_io_num_metric(metric_dim, metric_param)
        self.remove_restore_total_io_num_metric(metric_dim, metric_param)
        self.remove_restore_last_size_metric(metric_dim, metric_param)
        self.remove_restore_last_elapse_metric(metric_dim, metric_param)
        self.remove_restore_last_io_num_metric(metric_dim, metric_param)

    def remove_zk_metric(self, metric_dim, metric_param):
        self.remove_zookeeper_memory_use_metric(metric_dim, metric_param)
        self.remove_zookeeper_datadir_use_metric(metric_dim, metric_param)
        self.remove_zookeeper_memory_total_metric(metric_dim, metric_param)
        self.remove_zookeeper_datadir_total_metric(metric_dim, metric_param)

    @exception_catch
    def update_alarm(self, metric_name, label, value):
        self.log.info("update alarm %s[%s] = %d", metric_name, label, value)
        if metric_name == "server_pos_except":
            self.server_pos_except.labels(ip_addr=label['ip_addr']).set(value)
        elif metric_name == "server_papi_except_total":
            self.server_papi_except_total.labels(ip_addr=label['ip_addr']).inc(value)
        elif metric_name == "server_zk_except":
            self.server_zk_except.labels(ip_addr=label['ip_addr']).set(value)
        elif metric_name == "server_pos_version_except":
            self.server_pos_version_except.labels(ip_addr=label['ip_addr']).set(value)
        elif metric_name == "hard_cache_offline_total":
            self.hard_cache_offline_total.labels(ip_addr=label['ip_addr']).inc(value)
        elif metric_name == "hard_cache_io_timeout_total":
            self.hard_cache_io_timeout_total.labels(ip_addr=label['ip_addr']).inc(value)
        elif metric_name == "hard_snode_io_timeout_total":
            self.hard_snode_io_timeout_total.labels(ip_addr=label['ip_addr']).inc(value)
        elif metric_name == "hard_snet_timeout":
            self.hard_snet_timeout.labels(ip_addr=label['ip_addr']).set(value)
        elif metric_name == "hard_snet_except":
            self.hard_snet_except.labels(ip_addr=label['ip_addr']).set(value)
        elif metric_name == "hard_snet_failed":
            self.hard_snet_failed.labels(ip_addr=label['ip_addr']).set(value)
        elif metric_name == "pos_ckg_health_status":
            self.pos_ckg_health_status.labels(poolid=label['poolid']).set(value)
        elif metric_name == "soft_pool_rw_failed":
            self.soft_pool_rw_failed.labels(poolid=label['poolid']).set(value)
        elif metric_name == "soft_vdisk_unsevice":
            self.soft_vdisk_unsevice.labels(poolid=label['poolid'], vdiskid=label['vdiskid']).set(value)
        elif metric_name == "soft_vdisk_datacheck_failed":
            self.soft_vdisk_datacheck_failed.labels(poolid=label['poolid'], vdiskid=label['vdiskid']).set(value)
        elif metric_name == "soft_vdisk_datalog_pos_unservice":
            self.soft_vdisk_datalog_pos_unservice.labels(poolid=label['poolid'], vdiskid=label['vdiskid']).set(value)
        elif metric_name == "soft_vdisk_datalog_imperfect":
            self.soft_vdisk_datalog_imperfect.labels(cluster_id=self.DEFAULT_LABEL).set(value)
        elif metric_name == "soft_vdisk_datalog_check_failed":
            self.soft_vdisk_datalog_check_failed.labels(poolid=label['poolid'], vdiskid=label['vdiskid']).set(value)
        elif metric_name == "soft_scsi_much_to_latency_total":
            self.soft_scsi_much_to_latency_total.labels(poolid=label['poolid'], vdiskid=label['vdiskid'],
                                                        volumeid=label['volumeid'], snapshotid=label['snapshotid']).inc(value)
        elif metric_name == "soft_scsi_io_timeout_total":
            self.soft_scsi_io_timeout_total.labels(poolid=label['poolid'], vdiskid=label['vdiskid'], volumeid=label['volumeid'],
                                                   snapshotid=label['snapshotid']).inc(value)
        elif metric_name == "soft_scsi_io_failed_total":
            self.soft_scsi_io_failed_total.labels(poolid=label['poolid'], vdiskid=label['vdiskid'], volumeid=label['volumeid'],
                                                  snapshotid=label['snapshotid']).inc(value)
        elif metric_name == "resource_vdisk_capacity_unenough":
            self.resource_vdisk_capacity_unenough.labels(poolid=label['poolid'], vdiskid=label['vdiskid']).set(value)
        elif metric_name == "resource_volume_or_snapshot_unenough":
            self.resource_volume_or_snapshot_unenough.labels(poolid=label['poolid'], vdiskid=label['vdiskid'],
                                                             volumeid=label['volumeid']).set(value)
        elif metric_name == "resource_volume_or_snapshot_residual":
            self.resource_volume_or_snapshot_residual.labels(
                poolid=label['poolid'], vdiskid=label['vdiskid'], volumeid=label['volumeid'],
                snapshotid=label['snapshotid']).set(value)
        elif metric_name == "resource_hugepage_no_enough":
            self.resource_hugepage_no_enough.labels(ip_addr=label['ip_addr']).set(value)
        elif metric_name == "pos_disk_isolated_status":
            self.pos_disk_isolated_status.labels(node=label['node'], disk_sn=label['disk_sn'], ip_addr=label['ip_addr']).set(value)
        elif metric_name == "pos_subhealth_disk_smart":
            self.pos_subhealth_disk_smart.labels(node=label['node'], disk_sn=label['disk_sn'], ip_addr=label['ip_addr']).set(value)
        elif metric_name == "pos_subhealth_disk_smart_test":
            self.pos_subhealth_disk_smart_test.labels(node=label['node'], disk_sn=label['disk_sn'], ip_addr=label['ip_addr']).set(value)
        elif metric_name == "pos_subhealth_disk_temperature":
            self.pos_subhealth_disk_temperature.labels(node=label['node'], disk_sn=label['disk_sn'], ip_addr=label['ip_addr']).set(value)
        elif metric_name == "pos_subhealth_cache_smart":
            self.pos_subhealth_cache_smart.labels(node=label['node'], disk_sn=label['disk_sn'], ip_addr=label['ip_addr']).set(value)
        elif metric_name == "pos_subhealth_cache_smart_test":
            self.pos_subhealth_cache_smart_test.labels(node=label['node'], disk_sn=label['disk_sn'], ip_addr=label['ip_addr']).set(value)
        elif metric_name == "pos_subhealth_cache_temperature":
            self.pos_subhealth_cache_temperature.labels(node=label['node'], disk_sn=label['disk_sn'], ip_addr=label['ip_addr']).set(value)
        elif metric_name == "pos_subhealth_net_speed":
            self.pos_subhealth_net_speed.labels(node=label['node'], device=label['device'], ip_addr=label['ip_addr']).set(value)
        elif metric_name == "pos_subhealth_net_updown_times":
            self.pos_subhealth_net_updown_times.labels(node=label['node'], device=label['device'], ip_addr=label['ip_addr']).set(value)
        elif metric_name == "pos_subhealth_net_packet_drops":
            self.pos_subhealth_net_packet_drops.labels(node=label['node'], device=label['device'], ip_addr=label['ip_addr']).set(value)
        elif metric_name == "pos_subhealth_net_packet_errors":
            self.pos_subhealth_net_packet_errors.labels(node=label['node'], device=label['device'], ip_addr=label['ip_addr']).set(value)
        elif metric_name == "pos_subhealth_net_packet_loss_rate":
            self.pos_subhealth_net_packet_loss_rate.labels(node=label['node'], device=label['device'], ip_addr=label['ip_addr']).set(value)
        elif metric_name == "pos_subhealth_net_packet_delay_time":
            self.pos_subhealth_net_packet_delay_time.labels(node=label['node'], device=label['device'], ip_addr=label['ip_addr']).set(value)
        elif metric_name == "pos_subhealth_net_packet_jitter_time":
            self.pos_subhealth_net_packet_jitter_time.labels(node=label['node'], device=label['device'], ip_addr=label['ip_addr']).set(value)
        elif metric_name == "pos_external_storage_except":
            self.pos_external_storage_except.labels(ip_addr=label['ip_addr']).set(value)
        else:
            self.log.error("unknown alert: %s", metric_name)  # 输出信息“未知的告警指标XXXXX”

    @exception_catch
    def remove_alarm(self, metric_name, label):
        if metric_name == "server_pos_except":
            self.server_pos_except.remove(label['ip_addr'])
        elif metric_name == "server_zk_except":
            self.server_zk_except.remove(label['ip_addr'])
        elif metric_name == "server_pos_version_except":
            self.server_pos_version_except.remove(label['ip_addr'])
        elif metric_name == "hard_snet_timeout":
            self.hard_snet_timeout.remove(label['ip_addr'])
        elif metric_name == "hard_snet_except":
            self.hard_snet_except.remove(label['ip_addr'])
        elif metric_name == "hard_snet_failed":
            self.hard_snet_failed.remove(label['ip_addr'])
        elif metric_name == "pos_ckg_health_status":
            self.pos_ckg_health_status.remove(label['poolid'])
        elif metric_name == "soft_pool_rw_failed":
            self.soft_pool_rw_failed.remove(label['poolid'])
        elif metric_name == "soft_vdisk_unsevice":
            self.soft_vdisk_unsevice.remove(label['poolid'], label['vdiskid'])
        elif metric_name == "soft_vdisk_datacheck_failed":
            self.soft_vdisk_datacheck_failed.remove(label['poolid'], label['vdiskid'])
        elif metric_name == "soft_vdisk_datalog_pos_unservice":
            self.soft_vdisk_datalog_pos_unservice.remove(label['poolid'], label['vdiskid'])
        elif metric_name == "soft_vdisk_datalog_imperfect":
            self.soft_vdisk_datalog_imperfect.remove(self.DEFAULT_LABEL)
        elif metric_name == "soft_vdisk_datalog_check_failed":
            self.soft_vdisk_datalog_check_failed.remove(label['poolid'], label['vdiskid'])
        elif metric_name == "resource_vdisk_capacity_unenough":
            self.resource_vdisk_capacity_unenough.remove(label['poolid'], label['vdiskid'])
        elif metric_name == "resource_volume_or_snapshot_unenough":
            self.resource_volume_or_snapshot_unenough.remove(label['poolid'], label['vdiskid'], label['volumeid'])
        elif metric_name == "resource_volume_or_snapshot_residual":
            self.resource_volume_or_snapshot_residual.remove(label['poolid'], label['vdiskid'],
                                                             label['volumeid'], label['snapshotid'])
        elif metric_name == "resource_hugepage_no_enough":
            self.resource_hugepage_no_enough.remove(label['ip_addr'])
        elif metric_name == "pos_disk_isolated_status":
            self.pos_disk_isolated_status.remove(label['node'], label['disk_sn'], label['ip_addr'])
        elif metric_name == "pos_subhealth_disk_smart":
            self.pos_subhealth_disk_smart.remove(label['node'], label['disk_sn'], label['ip_addr'])
        elif metric_name == "pos_subhealth_disk_smart_test":
            self.pos_subhealth_disk_smart_test.remove(label['node'], label['disk_sn'], label['ip_addr'])
        elif metric_name == "pos_subhealth_disk_temperature":
            self.pos_subhealth_disk_temperature.remove(label['node'], label['disk_sn'], label['ip_addr'])
        elif metric_name == "pos_subhealth_cache_smart":
            self.pos_subhealth_cache_smart.remove(label['node'], label['disk_sn'], label['ip_addr'])
        elif metric_name == "pos_subhealth_cache_smart_test":
            self.pos_subhealth_cache_smart_test.remove(label['node'], label['disk_sn'], label['ip_addr'])
        elif metric_name == "pos_subhealth_cache_temperature":
            self.pos_subhealth_cache_temperature.remove(label['node'], label['disk_sn'], label['ip_addr'])
        elif metric_name == "pos_subhealth_net_speed":
            self.pos_subhealth_net_speed.remove(label['node'], label['device'], label['ip_addr'])
        elif metric_name == "pos_subhealth_net_updown_times":
            self.pos_subhealth_net_updown_times.remove(label['node'], label['device'], label['ip_addr'])
        elif metric_name == "pos_subhealth_net_packet_drops":
            self.pos_subhealth_net_packet_drops.remove(label['node'], label['device'], label['ip_addr'])
        elif metric_name == "pos_subhealth_net_packet_errors":
            self.pos_subhealth_net_packet_errors.remove(label['node'], label['device'], label['ip_addr'])
        elif metric_name == "pos_subhealth_net_packet_loss_rate":
            self.pos_subhealth_net_packet_loss_rate.remove(label['node'], label['device'], label['ip_addr'])
        elif metric_name == "pos_subhealth_net_packet_delay_time":
            self.pos_subhealth_net_packet_delay_time.remove(label['node'], label['device'], label['ip_addr'])
        elif metric_name == "pos_subhealth_net_packet_jitter_time":
            self.pos_subhealth_net_packet_jitter_time.remove(label['node'], label['device'], label['ip_addr'])
        elif metric_name == "pos_external_storage_except":
            self.pos_external_storage_except.remove(label['ip_addr'])
        else:
            self.log.error("unknown alert: %s", metric_name)
