# -*- coding: utf-8 -*-
import select, socket, time, sys

try:
    input = raw_input
except NameError:
    pass

ESCAPECHAR = "/"

def escape(string):
    string = string.replace(ESCAPECHAR,2*ESCAPECHAR)
    string = string.replace("\n",ESCAPECHAR+"\n")
    #string = string.replace("\r",ESCAPECHAR+"\r")
    return "/"+string+"\n"

def isescaped(string):
    return string.startswith(ESCAPECHAR)

def unescape(string):
    if not isescaped(string):
        print("tried to unescape string which wasn't escaped!!!")
        return None
    string = string[1:-1]
    #string = string.replace(ESCAPECHAR+"\r","\r")
    string = string.replace(ESCAPECHAR+"\n","\n")
    string = string.replace(2*ESCAPECHAR,ESCAPECHAR)
    return string

def isover(string):
    return (string.endswith("\n") and not string.endswith(ESCAPECHAR+"\n"))

class template(object):
    def __init__(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self,*args):
        self.close()
    def t_init(self):
        self.packagesize = 10000
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind(("", self.port))
        except socket.error as why:
            print("socket error: %s" % why)
            return
        else:
            pass
            #print "opened socket at port",self.port

    def send(self,msg,addr,doescape=True):
        if doescape:
            msg = escape(msg)
        elif msg.startswith(ESCAPECHAR):
            raise ValueError("unescaped messages may not start with ESCAPECHAR:%s" %ESCAPECHAR)
        self.socket.sendto(msg.encode(),addr)

    def close(self):
        self.socket.close()

class msgcache(dict):
    def __missing__(self,key):
        return ""

class server(template):
    def __init__(self, port=40001, name="NONAME", key="",
                 on_connect=None, on_disconnect=None):
        self.port = port
        self.name = name
        self.key = key
        self.msgcache = msgcache() #{addr:msg,...}
        self.t_init()
        self.clients = set()
        if on_connect:
            self.on_connect = on_connect
        else:
            self.on_connect = lambda addr:None
        if on_disconnect:
            self.on_disconnect = on_disconnect
        else:
            self.on_disconnect = lambda addr:None

    def receive(self):
        received=[]
        while select.select([self.socket], [], [],0.001)[0]:
            try:
                data, addr = self.socket.recvfrom(self.packagesize)
                data = data.decode()
            except:
                pass
            else:
                self.msgcache[addr]+=data
                msg = self.msgcache[addr]
                if msg.startswith("PING"):
                    print("got",msg)
                if msg == "PING"+self.key:
                    self.send("PONG"+self.name, addr, False)
                elif msg == "hi":
                    self.clients.add(addr)
                    self.on_connect(addr)
                elif msg == "bye":
                    if addr in self.clients:
                        self.clients.remove(addr)
                        self.on_disconnect(addr)
                elif isover(msg):
                    msg = unescape(msg)
                    if msg != None:
                        received.append((msg,addr))
                else:
                    continue
                self.msgcache[addr] = ""
        return received

    def get_clients(self):
        return self.clients

    def close(self):
        for addr in self.get_clients():
            self.socket.sendto("shutdown",addr)
        self.socket.close()


class client(template):
    def __init__(self,serveraddr,port=40000):
        self.port = port
        self.serveraddr = serveraddr
        self.t_init()
        self.answer = ""
        self.send("hi",False)

    def ask(self,msg,timeout=1):
        """Send msg to server and return first answer from server"""
        self.send(msg)
        return self.receive(timeout)

    def send(self,msg,escape=True):
        super(client,self).send(msg,self.serveraddr,escape)

    def receive(self,timeout=1,between_messages_timeout=0.01):
        """
        returns False if nothing is received within timeout, else return latest complete message
        """
        answer = self.answer
        result = False
        to = timeout
        while True:
            if select.select([self.socket],[],[],to)[0]:
                to = timeout
                try:
                    data, addr = self.socket.recvfrom(self.packagesize)
                    data = data.decode()
                except:
                    raise Exception("Disconnect")
                if addr == self.serveraddr:
                    answer+=data
                    if answer == "shutdown":
                        raise Exception("Server went down.")
                    if isover(answer):
                        answer = unescape(answer)
                        if answer != None:
                            result = answer
                        to = between_messages_timeout
                        answer = ""
            else:
                break
        self.answer = answer
        return result

    def close(self):
        self.send("bye",False)
        self.socket.close()

def search_servers(waittime=1,port=40001,key=""):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        print(type(key))
        s.sendto(("PING"+key).encode(), ("<broadcast>", port))
    except socket.error as why:
        s.close()
        return []

    servers = []
    while select.select([s], [], [], waittime)[0]:
        data, addr = s.recvfrom(100)
        data = data.decode()
        if data.startswith("PONG") and not addr[0] in servers:
            #try:
            #    name = socket.gethostbyaddr(addr[0])[0] + " (" + addr[0] + ")"
            #except socket.error:
            #    name = addr[0]
            #clients.append((name,data[4:]))
            servers.append((addr,data[4:]))
    s.close()
    return servers

if __name__ == "__main__":
    while True:
        eingabe = input(">>> ")
        if eingabe == "quit":
            break

        if eingabe == "search":
            servers = search_servers(key="bot-arena")
            if servers != []:
                for i,(addr,name) in enumerate(servers):
                    print(i, name, addr)
            else:
                print("no servers found")

        if eingabe == "client":
            print("spiel gestartet")
            servers = search_servers(key="bot-arena")
            if servers != []:
                addr,name = servers[0]
                print("connecting to server %s" %name)
                c = client(addr)
                while True:
                    eingabe = input("send@server: ")
                    if eingabe == "close":
                        break
                    print(c.ask(eingabe))
                c.close()
            else:
                print("no server found")
        
        if eingabe == "server":
            s = server()
            while True:
                for msg,addr in s.receive():
                    print("received:",repr(msg))
                    reply = "reply:"+msg
                    s.send(reply,addr)
                    if msg == "shutdown":
                        break
                else:
                    continue
                break
            s.close()

        if eingabe == "help":
            print("""
search: searchs for computers and connects to them
client: connect with first server to find
server: starts server
quit  : stops programm
""")
