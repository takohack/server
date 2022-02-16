import json
import logger
import threading
import socket
from time import sleep, time
from uuid import uuid4
from singleton import Singleton


@Singleton
class Mcast(object):
    APP_MTU = 1400
    MCAST_PORT = 9014
    MCAST_KEY = '_mcast_upd'

    def __init__(self, port=None) -> None:
        super().__init__()
        self._mcast_dat = {}
        self._port = port or self.MCAST_PORT
        self._get_all_ip_list = []
        self._sock = None
        self._callback = {}
        self._wait_ack = None
        self._snd_cnt = 0
        self._raw = None
        self._rcv_pri_req = None
        self._tx_srv = None
        self._rx_srv = None
        self._slock = threading.Lock()
        self.log = logger.Logger()

    def info(self, fmt, *arg):
        self.log.info(fmt, *arg)

    def warn(self, fmt, *arg):
        self.log.warn(fmt, *arg)

    def _get_mem_ip_list(self):
        if callable(self._get_all_ip_list):
            return self._get_all_ip_list()
        return self._get_all_ip_list

    def _get_mcat_udp(self) -> socket.socket:
        if self._sock is None:
            def _make_mcast_udp(sport) -> socket.socket:
                ANY = "0.0.0.0"
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                # 绑定监听多播数据包的端口
                s.bind((ANY, sport))
                s.setblocking(True)
                return s

            self._sock = _make_mcast_udp(self._port)
        return self._sock

    def _udp_send(self, sock: socket.socket, chnn, key, ip, dat, seq, off, total_len, need_ack, sctrl=True):
        val = json.dumps([chnn, key, seq, off, total_len, dat, need_ack], separators=(',', ':')).encode()
        if not isinstance(ip, (list, tuple)):
            ip = (ip,)
        for x in ip:
            self._slock.acquire()
            len = sock.sendto(val, (x, self.MCAST_PORT))
            self._slock.release()
            if len <= 0:
                self.warn('udp_send', len, ip)
            if not sctrl:
                continue
            self._snd_cnt += 1
            if self._snd_cnt > 60:
                self._snd_cnt = 0
                sleep(0.001)

    def _udp_send_seg(self, sock, chnn, key, ip, seg, need_ack, sctrl=True):
        seq, i, j, dat = seg[0], seg[1], seg[2], seg[3]
        self._udp_send(sock, chnn, key, ip, dat, seq, i, j, need_ack, sctrl=sctrl)

    def _build_msg(self, segs: dict):
        msg = []
        for key in sorted(segs.keys()):
            msg.append(segs[key])
            # 接受完的消息及时释放,只留key做重复包过滤
            segs[key] = None
        return ''.join(msg)

    def _recv_complete(self, ip: str, chnn: str, key: str, segs: dict):
        cbs = self._callback.get(chnn, [])[:]
        msg = self._build_msg(segs)
        for cb in cbs:
            cb(ip, key, msg)

    def _show_err(self):
        import sys
        import traceback
        exc_type, exc_value, exc_obj = sys.exc_info()
        traceback.print_tb(exc_obj)
        print(exc_type, exc_value)

    def work_loop(self, sock):
        """
        @description: 服务程序主体, 会堵塞, 应启动一个线程来调用
        @param {sock} udp-sock
        @note {}   需要等本函数运行之后, 才可以调用send, 如果是线程启动本函数之后,不要sleep(0.1)后才可以调用send
        @return {*}
        """
        clear_tm = 0
        all_wait_req = {}

        def clear_old_wait_req_per_1s():
            nonlocal clear_tm
            now = time()
            if now - clear_tm < 1:
                return
            clear_tm = now
            seqs = []
            for seq, req in all_wait_req.items():
                if req[0] - now > 20:
                    seqs.append(seq)
            for seq in seqs:
                del all_wait_req[seq]

        last_of = 0
        cache = []
        ack_seq = {}
        while self._wait_ack is not None:
            clear_old_wait_req_per_1s()

            def send_msg(chnn, key, ip, seg, need_ack):
                self._udp_send_seg(sock, chnn, key, ip, seg, need_ack, sctrl=False)

            try:
                if not cache:
                    cache = self._raw
                    self._raw = []
                if not cache:
                    sleep(0.1)
                    continue
                ip, dat = cache.pop(0)
                pk = json.loads(dat)
                if pk and len(pk) == 7:
                    chnn, key, seq, off, total, msg, need_ack = pk[0], pk[1], pk[2], pk[3], pk[4], pk[5], pk[6]
                    if total == 0:  # 应答包
                        wait_mgr = self._wait_ack.get(seq, None)
                        if wait_mgr is None:  # 发送函数已经放弃
                            continue
                        # _debug_msg("slice-ok", msg[:3], ip)
                        wait_ack, evt = wait_mgr
                        # tout, tx_win, win_sz, offset, err_times
                        dats = wait_ack.get(ip, [])
                        dats[0] = 0
                        # 错误清零
                        dats[4] = 0
                        # 清理发送窗口
                        dats[1] = [x for x in dats[1] if x[0] not in msg]
                        # 调整发送窗口大小
                        dats[2] = 1000
                        # 通知发送线程处理结果
                        evt.set()
                        # _debug_msg("notify", msg[:3], ip)
                        continue
                    wait_req = all_wait_req.get(seq, None)
                    if wait_req is None:
                        wait_req = [time(), {}, 0]
                        all_wait_req[seq] = wait_req
                        ack_seq[seq] = set({})
                        last_of = 0
                    elif last_of + self.APP_MTU != off:
                        self.warn("not-continue", last_of // self.APP_MTU, off // self.APP_MTU)
                    last_of = off
                    segs = wait_req[1]
                    new_seg = False
                    if off not in segs:
                        # _debug_msg("slice-recv", off, ip)
                        new_seg = True
                        wait_req[2] += len(msg)
                    else:
                        self.warn("slice-recv-same", off, ip)
                    segs[off] = msg
                    ack = ack_seq[seq]
                    ack: set
                    ack.add(off)
                    if need_ack or len(ack) >= 100:
                        list_ack = list(ack)
                        send_msg(chnn, key, ip, (seq, off, 0, list_ack), False)
                        ack.clear()
                    if new_seg:
                        if wait_req[2] == total:
                            self._recv_complete(ip, chnn, key, segs)

                    if self._rcv_pri_req:
                        self._rcv_pri_req = False
                        sleep(0.001)
            except OSError:
                if self._wait_ack is None:
                    self.info('work exit now')
                    break
                self._show_err()
            except Exception:
                self._show_err()
                pass
            else:
                continue
            sleep(1)

    def recv_loop(self, sock):
        while self._wait_ack is not None:
            try:
                self._rcv_pri_req = True
                dat, addr = sock.recvfrom(2048)
                ip = addr[0]
                self._raw.append((ip, dat))
            except OSError:
                if self._wait_ack is None:
                    self.info('recv exit now')
                    return
            except Exception:
                pass
            else:
                continue
            self._show_err()
            sleep(1)

    def send_msg(self, chnn: str, key: str, msg: str, ip=None):
        """
        @description:      报文的发送
        @param {*} chnn    消息通道
        @param {*} key     消息唯一标识
        @param {str} msg   消息
        @param {*} ip      发送的目的ip, 当ip=None时表示所有节点
        @return {*}        返回为发送成功的列表[],  None-表示出现了异常
        """
        if not self.is_running():
            self.warn(f'send err: mcast server not running ({id(self)})')
            return None
        seq = str(uuid4())
        try:
            sock = self._get_mcat_udp()
            if sock is None:
                self.warn(f'send err: mcast server sock not open ({id(self)})')
                return None

            if ip is None:
                ip_list = self._get_mem_ip_list()
            elif isinstance(ip, (list, tuple)):
                ip_list = ip
            else:
                ip_list = (ip,)

            def send_msg(dst_ip, seg, need_ack):
                self._udp_send_seg(sock, chnn, key, dst_ip, seg, need_ack)

            now = time()
            # wait_ack:  tout, tx_win, win_sz, offset, err_times
            wait_ack = {k: [now, [], 1, 0, 0] for k in ip_list}
            evt = threading.Event()
            self._wait_ack[seq] = (wait_ack, evt)
            tlen = len(msg)

            def get_slice(offset):
                num = min(self.APP_MTU, tlen - offset)
                return offset, num

            def fill_win(dst_ip, dats):
                tx_win, win_sz, offset, err_times = dats[1], dats[2], dats[3], dats[4]
                if err_times > 3:
                    win_sz = 1
                now = time()
                while len(tx_win) < win_sz:
                    offset, num = get_slice(offset)
                    if num == 0:
                        break
                    tx_win.append([offset, num, 0])
                    offset += num
                dats[3] = offset
                segs = []
                for i in range(len(tx_win)):
                    ack = i + 1 >= win_sz
                    offset, num, tm = tx_win[i]
                    if now > tm:
                        seg = (seq, offset, tlen, msg[offset:offset + num])
                        tx_win[i][2] = now + 0.5
                        segs.append(seg)
                    if ack:
                        break
                if segs:
                    last = segs[-1]
                    for seg in segs:
                        send_msg(dst_ip, seg, seg == last)
                    # _debug_msg("slice-tx", len(segs), segs[0][1])
                dats[0] = now + 0.5

            for ip, dats in wait_ack.items():
                fill_win(ip, dats)

            while True:
                now = time()
                pending = False
                fail_ip = []
                for ip, dats in wait_ack.items():
                    tout, tx_win, _, offset, err_times = dats
                    has_dat_to_tx = (offset < tlen or len(tx_win))
                    if not has_dat_to_tx:
                        continue
                    fail_ip.append(ip)
                    if err_times >= 5:
                        continue
                    pending = True
                    if now <= tout:
                        continue
                    if has_dat_to_tx:
                        fill_win(ip, dats)
                        dats[4] = err_times + 1
                if not pending:
                    # _debug_msg("send-ok", len(msg), ok)
                    self.info(f'mcast send chan={chnn} key={key} to={ip_list}, fail={fail_ip}')
                    return fail_ip
                evt.wait(0.2)
                evt.clear()
        except Exception:
            self._show_err()
        finally:
            self._wait_ack.pop(seq)
        self.warn('mcast send chan=%s key=%s failed', chnn, key)
        return None

    def register_listener(self, chnn: str, callback: callable):
        """
        @description: 注册数据监听
        @param {*} chnn       字符串, 唯一标识一个数据通道
        @param {*} callback   监听回调, callable(ip, key, msg),   key为消息唯一标识, msg为具体消息
        @return {*}           无
        """
        if self._callback.get(chnn, None) is None:
            self._callback[chnn] = []
        self._callback[chnn].append(callback)

    def start_server(self, get_all_ip_list):
        if self.is_running():
            self.warn('mcast is running ...')
            return False
        sock = self._get_mcat_udp()
        if sock is None:
            self.warn('open socket faild ...')
            return False
        self.info(f'mcast starting ... ({id(self)})')
        self._wait_ack = {}
        self._raw = []
        self._get_all_ip_list = get_all_ip_list

        self._tx_srv = threading.Thread(target=self.work_loop, args=(sock,))
        self._rx_srv = threading.Thread(target=self.recv_loop, args=(sock,))
        self._rx_srv.start()
        self._tx_srv.start()
        return True

    def stop_server(self):
        if not self.is_running():
            self.warn('mcast not running ...')
            return False
        self.info(f'mcast stopping ...({id(self)})')
        self._wait_ack = None
        sock = self._sock
        if sock is not None:
            self._sock = None
            sock.close()
        self._tx_srv.join()
        self._rx_srv.join()
        self._tx_srv = None
        self._rx_srv = None

    def is_running(self):
        return self._tx_srv is not None


if __name__ == '__main__':
    from hashlib import md5

    print('test_begin')

    def get_ip_list():
        # return ['172.20.104.221', '172.24.37.7']
        return ['172.20.104.221']

    def on_recv_test(ip, key, msg):
        print(key, ip, 'over')
        print('on_recv_test', key, md5(msg.encode()).hexdigest())

    _mcast = Mcast()
    _mcast.start_server(get_ip_list)

    chnn = 'test'
    _mcast.register_listener(chnn=chnn, callback=on_recv_test)
    msg = str(uuid4()) * 30 * 1024 * 10
    print("send", md5(msg.encode()).hexdigest())
    _mcast.send_msg(chnn, 'msg-1', msg)

    # 1M ~= 0.24s   10M ~= 1.8s 100M ~= 13s
    _mcast.stop_server()

    print('test_over')
