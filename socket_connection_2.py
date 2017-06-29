# TODO: nameserver to python3 (unicode encode decode stuff)

import socket
import select
import zlib
import ast
import sys

import time
import random
import itertools

if sys.version < "3":
    import thread
else:
    import _thread as thread

PACKAGESIZE = 1024

ESCAPECHAR = b"/"
SPLITSEQUENCE = b" "+ESCAPECHAR+b" " #single escape char can mark end of message, cause other occurrences of it will be replaced by 2 escapechars
SPLITLENGTH = len(SPLITSEQUENCE)

def escape(string):
    string = zlib.compress(string)
    string = string.replace(ESCAPECHAR,2*ESCAPECHAR)
    return string+SPLITSEQUENCE

def unescape(string):
    string = string.replace(2*ESCAPECHAR,ESCAPECHAR)
    if string.endswith(SPLITSEQUENCE):
        string = string[:-SPLITLENGTH]
    return zlib.decompress(string)

class Disconnect(Exception):
    pass

uncomplete_msgs = {} #socket:msg_head

def send_msg(sock,msg): #M# maybe do async send?
    try:
        sock.sendall(escape(msg.encode()))
    except socket.error as e:
        print (e, "in send")

def recv_msg(sock):
    """returns message, None or raises Disconnect"""
    try:
        msg = sock.recv(PACKAGESIZE)
    except socket.error as e:
        print (e)
        raise Disconnect()
    if msg == b"":
        raise Disconnect()
    msg_head = uncomplete_msgs.get(sock,b"")
    splitpos = (msg_head[-SPLITLENGTH:].rjust(SPLITLENGTH,ESCAPECHAR)+msg).find(SPLITSEQUENCE)
    if splitpos != -1:
        completed_msg = msg_head + msg[:splitpos]
        uncomplete_msgs[sock] = msg[splitpos:]
        return unescape(completed_msg).decode()
    uncomplete_msgs[sock] = msg_head + msg
    return None

class symmetric_addr_socket_mapping(object):
    def __init__(self):
        self._addr_to_socket = dict()
        self._socket_to_addr = dict()

    def set(self,addr,socket):
        if addr in self._addr_to_socket:
            print ("socket already taken")
            return False
        if socket in self._socket_to_addr:
            print ("addr already taken")
            return False
        self._addr_to_socket[addr] = socket
        self._socket_to_addr[socket] = addr
        return True

    def addrs(self):
        return self._addr_to_socket.keys()

    def sockets(self):
        return self._socket_to_addr.keys()

    def items(self):
        """[(socket,addr),...]"""
        return self._socket_to_addr.items()

    def get_socket(self,addr):
        return self._addr_to_socket[addr]

    def get_addr(self,socket):
        return self._socket_to_addr[socket]

    def pop_by_addr(self,addr):
        socket = self._addr_to_socket.pop(addr)
        self._socket_to_addr.pop(socket)
        return socket

    def pop_by_socket(self,socket):
        addr = self._socket_to_addr.pop(socket)
        self._addr_to_socket.pop(addr)
        return addr

class template(object):
    def __enter__(self):
        return self

    def __exit__(self,*args):
        self.close()

class client(template):
    def __init__(self,serveraddr):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect(serveraddr)

    def ask(self,msg,timeout=1):
        self.send(msg)
        return self.receive(timeout)

    def send(self,msg):
        send_msg(self.socket,msg)

    def receive(self,timeout=0.001):
        while select.select([self.socket],[],[],timeout)[0]:
            msg = recv_msg(self.socket)
            if msg:
                return msg
        return False

    def close(self):
        self.socket.close()

class server(template):
    def __init__(self, port=40000, name="NONAME", key="",
                     on_connect=None, on_disconnect=None, nameserveraddr=None, nameserver_refresh_interval=10):
        # save parameters
        self.port = port
        self.name = name
        self.key = key
        self.on_connect = on_connect or (lambda addr:None)
        self.on_disconnect = on_disconnect or (lambda addr:None)
        self.nameserveraddr = nameserveraddr
        self.nameserver_refresh_interval = nameserver_refresh_interval

        random.seed()
        self.uid = random.getrandbits(32)

        # declare some attributes
        self.clients = symmetric_addr_socket_mapping() #addr:socket
        self.new_connected_clients = [] # msg_socket, addr
        self.closed = False

        # Socket for replying to Broadcasts
        self.info_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.info_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            socket.SO_REUSEPORT
        except AttributeError:
            pass
        else:
            self.info_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self.info_socket.bind(("", self.port))

        # Socket for creating client sockets
        self.entry_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.entry_socket.bind(("",0))
        self.entry_socket.listen(5)

        # Start threads
        thread.start_new_thread(self._info_thread,())
        thread.start_new_thread(self._entry_thread,())
        if self.nameserveraddr:
            thread.start_new_thread(self._register_thread,())


    def _info_thread(self):
        port = str(self.entry_socket.getsockname()[1])
        while not self.closed:
            try:
                if select.select([self.info_socket],[],[],1)[0]:
                    msg, addr = self.info_socket.recvfrom(PACKAGESIZE) #buffer size could be smaller, but who cares
                    if self.closed:
                        break
                    print (repr(msg.decode()),repr("PING "+self.key))
                    if msg.decode() == "PING "+self.key:
                        print("ponging")
                        self.info_socket.sendto(("PONG %s %s %s" %(port,self.uid,self.name)).encode(),addr)
                        print("gepongt")
            except Exception as e:
                print (e, "in _info_thread")
        self.info_socket.close()
    
    def _entry_thread(self):
        while not self.closed:
            try:
                if select.select([self.entry_socket],[],[],1)[0]:
                    client = self.entry_socket.accept()
                    if self.closed:
                        break
                    self.new_connected_clients.append(client)
            except Exception as e:
                print (e, "in _entry_thread")
        self.entry_socket.close()

    def _register_thread(self):
        while not self.closed:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(self.nameserveraddr)
                s.send("register %s %s" %(self.port,self.key))
                s.close()
            except Exception as e:
                print (e, "in _register_thread")
            time.sleep(self.nameserver_refresh_interval)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(self.nameserveraddr)
            s.send("unregister %s %s" %(self.port,self.key))
            s.close()
        except Exception as e:
            print (e, "in _register_thread")

    def send(self,msg,addr):
        self.update()
        client_socket = self.clients.get_socket(addr)
        if client_socket:
            send_msg(client_socket,msg)
        else:
            raise ValueError("no connection to %s available")

    def receive(self,timeout = 0.001):
        self.update()
        msgs = []
        while True:
            client_sockets = self.clients.sockets()
            if not client_sockets:
                break
            ready_client_sockets = select.select(client_sockets, [], [], timeout)[0] # maybe affected by crashing clients? Not happened yet.
            if not ready_client_sockets:
                break
            for client_socket in ready_client_sockets:
                addr = self.clients.get_addr(client_socket)
                try:
                    msg = recv_msg(client_socket)
                except Disconnect:
                    self.clients.pop_by_addr(addr)
                    uncomplete_msgs.pop(client_socket,None)
                    msgs = [(m,a) for (m,a) in msgs if a != addr]
                    self.on_disconnect(addr)
                    continue
                if msg:
                    msgs.append((msg,addr))
            #M# do more sophisticated stuff here later for infinitely long messages
        return msgs
            

    def update(self):
        while self.new_connected_clients:
            socket, addr = self.new_connected_clients.pop(0)
            if self.clients.set(addr,socket):
                self.on_connect(addr)
            else:
                socket.close()
                print("double login from same address")

    def get_clients(self):
        return self.clients.addrs()

    def close(self):
        self.closed = True
        for client_socket,addr in itertools.chain(self.clients.items(),self.new_connected_clients):
            client_socket.close()
            uncomplete_msgs.pop(client_socket,None)
            self.on_disconnect(addr)

class nameserver(template):
    def __init__(self, port, timetolive = 20):
        """listen on port, entrys expire after timetolife (should be longer than nameserver_refresh_interval of servers)"""
        self.timetolive = timetolive
        self.known_servers = {} #(key,addr):timestamp
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(("",port))
        self.socket.listen(5)

    def update(self):
        for key,timestamp in self.known_servers.items():
            if time.time()-timestamp > self.timetolive:
                self.known_servers.pop(key)

    def handle(self,msg,addr):
        """
        msg of one of the forms:
        list key
        register port key
        unregister port key
        """
        if msg.startswith("list"):
            parts = msg.split(" ",1)
            if len(parts) == 2:
                _,req_key = parts
                return repr([addr for key,addr in self.known_servers.keys() if key == req_key])
            return None

        if msg.startswith("register") or msg.startswith("unregister"):
            parts = msg.split(" ",2)
            if len(parts) == 3:
                _,port,key = parts
                try:
                    port = int(port)
                except TypeError:
                    return None
                serveraddr = (addr[0],port)
                dict_key = (key,serveraddr)
                if msg.startswith("register"):
                    self.known_servers[dict_key] = time.time()
                else:
                    if dict_key in self.known_servers:
                        self.known_servers.pop(dict_key)
            return None

    def loop(self,waittime=1):
        while True:
            client, addr = self.socket.accept()
            try:
                msg = client.recv(PACKAGESIZE)
                print (self.known_servers)
                self.update()
                print (self.known_servers)
                answer = self.handle(msg,addr)
                print (self.known_servers)
                if answer:
                    client.sendto(answer,addr)
            finally:
                client.close()

    def close(self):
        self.socket.close()

class server_searcher(template):
    def __init__(self,port=40000,key="",nameserveraddr=None):
        self.port = port
        self.key = key
        self.nameserveraddr = nameserveraddr
        
        self.servers = [] # addr,port,uid,name,timestamp
        self.uids = set()
        self.closed = False
        
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        self.send_requests()
        thread.start_new_thread(self._receive_thread,())
    
    def send_requests(self):
        self._ping_task(("localhost"  , self.port))
        self._ping_task(("<broadcast>", self.port))
        if self.nameserveraddr:
            thread.start_new_thread(self._nameserver_task,())

    def _nameserver_task(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(self.nameserveraddr)
            s.send("list "+self.key)
            msg = ""
            while select.select([s],[],[],1)[0]:
                part = s.recv(PACKAGESIZE)
                if part == "":
                    break
                msg += part
            try:
                serveraddrs = ast.literal_eval(msg)
            except:
                print ("strange answer from name server")
                print (msg)
            else:
                for addr in serveraddrs:
                    self._ping_task(addr)
        except Exception as e:
            print (e, "nameserver nicht erreichbar")
        finally:
            s.close()

    def _ping_task(self,addr):
        print ("pinging",addr)
        try:
            self.socket.sendto(("PING "+self.key).encode(), addr)
        except socket.error as e:
            print (e)

    def _receive_thread(self):
        while not self.closed:
            try:
                if select.select([self.socket], [], [], 1)[0]:
                    data, addr = self.socket.recvfrom(PACKAGESIZE)
                    print(data)
                    pong, port, uid, name = (data.split(b" ",3)+[None,None,None])[:4]
                    ip = addr[0]
                    if pong != b"PONG":
                        continue
                    try:
                        port = int(port)
                    except ValueError:
                        print ("non integer port",data)
                        continue
                    if uid in self.uids:
                        continue
                    self.servers.append((addr,port,uid,name,time.time()))
                    self.uids.add(uid)
            except Exception as e:
                print ("hey",e)

    def get_servers(self):
        return [((addr[0],port),name) for addr,port,uid,name,timestamp in self.servers]
        
    def close(self):
        self.closed = True
        self.socket.close()

def search_servers(waittime=1,port=40000,key="",nameserveraddr=None):
    with server_searcher(port,key,nameserveraddr) as s:
        time.sleep(waittime)
        return s.get_servers()

if __name__ == "__main__":
    with nameserver(40001) as s:
        s.loop()
