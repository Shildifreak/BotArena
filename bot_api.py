import socket_connection_2 as socket_connection
import random
import sys
if sys.version < "3":
    input = raw_input

class Bot(object):
    def __init__(self):
        servers = socket_connection.search_servers(key="bot-arena")
        if not servers:
            raise RuntimeError("could not connect to bot-arena, since none was found")
        if len(servers) == 1:
            i = 0
        else:
            i = select([name for addr,name in servers])
        addr,name = servers[i]
        #addr,name = random.choice(servers)
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

def select(options):
    """
    Return (index, option) the user choose.
    """
    if not options:
        raise ValueError("no options given")
    print ("\n".join([" ".join(map(str,option)) for option in enumerate(options)]))
    m = "Please enter one of the above numbers to select:"
    while True:
        i = raw_input(m)
        try:
            return int(i), options[int(i)]
        except ValueError:
            m = "Please enter one of the above NUMBERS to select:",
        except IndexError:
            m = "Please enter ONE OF THE ABOVE numbers to select:",

