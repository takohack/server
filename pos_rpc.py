# _*_ coding:utf-8 _*_
# refactor on:2020/9/21 15:11
# Author   :youweisheng

import socket
import json
import uuid
import time


class JSONRPCException(Exception):
    def __init__(self, message):
        self.message = message


class JSONRPCClient(object):
    def __init__(self, addr, port=None, verbose=False, timeout=60.0):
        self.addr = addr
        self.MAX_RECV_LEN = 4096
        self.verbose = verbose
        self.timeout = timeout
        try:
            if addr.startswith('/'):
                self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.sock.connect(addr)
            elif ':' in addr:
                for res in socket.getaddrinfo(addr, port, socket.AF_INET6, socket.SOCK_STREAM, socket.SOL_TCP):
                    af, socktype, proto, canonname, sa = res
                self.sock = socket.socket(af, socktype, proto)
                self.sock.connect(sa)
            else:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((addr, port))
        except socket.error as ex:
            raise JSONRPCException("Error while connecting to %s\n"
                                   "Error details: %s" % (addr, ex))

    def __del__(self):
        self.sock.close()

    def call(self, method, params={}, verbose=False):
        req = {'jsonrpc': '2.0', 'method': method}
        struuid = str(uuid.uuid4())
        req['id'] = struuid
        if params:
            req['params'] = params
        reqstr = json.dumps(req)

        verbose = verbose or self.verbose

        if verbose:
            print("request:")
            print(json.dumps(req, indent=2))
        print(reqstr)

        self.sock.sendall(reqstr.encode("utf-8"))
        buf = ''
        closed = False
        response = {}
        start_time = time.clock()

        while not closed:
            try:
                timeout = self.timeout - (time.clock() - start_time)
                # print timeout
                if timeout <= 0.0:
                    break
                self.sock.settimeout(timeout)
                newdata = self.sock.recv(self.MAX_RECV_LEN)
                if newdata == b'':
                    closed = True
                buf += newdata.decode("utf-8")
                print(buf)
                response = json.loads(buf)
            except socket.timeout:
                break
            except ValueError:
                continue  # incomplete response; keep buffering
            break

        if not response:
            if method == "kill_instance":
                return {}
            if closed:
                msg = "Connection closed with partial response:"
            else:
                msg = "Timeout while waiting for response:"
            msg = "\n".join([msg, buf])
            raise JSONRPCException(msg)
        if 'error' in response:
            msg = "\n".join(["Got JSON-RPC error response",
                             "request:",
                             json.dumps(req, indent=2),
                             "response:",
                             # json.dumps(response)])
                             json.dumps(response['error'], indent=2)])
            raise JSONRPCException(msg)

        if verbose:
            print("response:")
            print(json.dumps(response, indent=2))

        return response['result']

    def get_scsi_info(self):
        response = self.call(method="GetPosStats", params={"GroupName": "scsi"})
        if 'GroupStats' in response:
            return response['GroupStats']
        else:
            return None

    def get_cache_info(self):
        response = self.call(method="GetPosStats",
                             params={"GroupName": "cache", "StatsName": "/public/cache_stats"})
        if 'StatsInfo' in response and 'CacheVdisk' in response['StatsInfo']:
            return response['StatsInfo']['CacheVdisk']
        else:
            return None

    def get_capacity_info(self):
        response = self.call(method="GetPosStats", params={"GroupName": "capacity"})
        if 'GroupStats' in response:
            return response['GroupStats']
        else:
            return None


class JSONRPCEmeiClient(object):
    def __init__(self, addr, port, verbose=False):
        self.addr = addr
        self.port = port
        self.verbose = verbose

    def call(self, method, params=None):
        import emei.framework.client as client
        addr = self.addr
        port = self.port
        namespace = "p-deployer"
        version = "1.0"
        content = {"jsonrpc": "2.0", "method": method, "id": 1}
        if params:
            content['params'] = params
        try:
            res = client.call(addr, port, method, namespace, content, version)
            return res.content['result']
        except Exception as e:
            raise JSONRPCException("rpc call %s failed: addr=%s e=%s" % (method, addr, repr(e)))
