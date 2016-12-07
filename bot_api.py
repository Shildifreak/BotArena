import socket_connection
import random

class Bot(object):
    def __init__(self):
        servers = socket_connection.search_servers(key="bot-arena")
        if not servers:
            raise RuntimeError("could not connect to bot-arena, since none was found")
        addr,name = random.choice(servers)
        print("connecting to server %s" %name)
        self.client = socket_connection.client(addr)

    def __enter__(self):
        return self

    def __exit__(self,*args):
        self.close()

    def close(self):
        self.client.close()


    def do(self,cmd):
        """for possible commands see robo_commands_doc.txt"""
        return self.client.ask(cmd)
