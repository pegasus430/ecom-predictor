#!/usr/bin/env python
import logging
import sqlite3
import os
import datetime
import re
import web_runner.db

LOG = logging.getLogger(__name__)

LB_ROUND_ROBIN = 'ROUND_ROBIN'

'''
Load balancer module to handle request on Web Runner REST Server
'''

'''
TODO and problems to solve:
. There's a memory leak
. db maitenance
'''

def getLB(method, **kwargs):
    '''Returns a LBInterface object according the LB method

    kwargs are the custom LB method parameters
    '''
    if method == LB_ROUND_ROBIN:
        return LBRoundRobin(**kwargs)


def getLB_from_config(config):
    '''Returns a LBInterface object with a Pyramid config file configuration'''

    try:
        lb_schedule_conf = config['lb.schedule']
    except KeyError:
        raise Exception("Load Balancer scheduler not in configuration")

    lb_db_file = config.get('lb.db', None)

    if lb_schedule_conf == 'round_robin':
        lb_schedule = LB_ROUND_ROBIN

        # Get the target servers
        config_servers = ( config[x] for x in config.keys() 
                             if x.startswith('lb.server.'))
        serv_re = re.compile(r'^\s*([\w\.-]+)(:?(\d+))?\s*$')
        lb_servers = []
        for config_server in config_servers:
            re_output = serv_re.match(config_server)
            if re_output:
                server = LBServer(*re_output.group(1,3))
                lb_servers.append(server)

        kwargs = {'servers': lb_servers, 'db': lb_db_file}
    else:
        raise Exception("Load Balancer scheduler %s not available" %
          lb_schedule_conf)

    return getLB(lb_schedule, **kwargs)


class LBServer(object):
    '''Object that represents a LB Server

    Attributes:
      . host
      . port
    '''
    def __init__(self, host=None, port=None, serial=None):
        if serial:
            (host, port) = serial.split('|', 1)
            self.host = host
            if port:
                self.port = int(port)
            else:
                self.port = None
        else:
            self.host = host
            self.port = port

    def serialize(self):
        host = self.host if self.host else ""
        port = str(self.port) if self.port else ""
        return "%s|%s" % (host, port)


class LBInterface(object):
    '''Base class to handle schedule LB assignament
    
    This class implements the core of the LB distribution and assignament.
    This class must be extended to implement the method get_new_server.
    That method receives a Pyramid request object and returns a LB
    server assigned for the task.
    '''
    
    def __init__(self, method, servers, db=None):
        self.lbMethod = method
        self.servers = servers
        self.ids = {}
        self.ids_date = {}
        self.lbdb = None

        if db:
            self.lbdb = web_runner.db.Lbdb(db, recreate=False)
            self.lbdb.create_dbstructure()
        
    def get_new_server(self, request):
        '''Method to be extended'''
        raise NotImplementedError

    def set_id(self, id, server):
        '''Relate an id with a specific server'''

        if self.lbdb:
            # Use the LB DB
            self.lbdb.set_rb_id(id, server.serialize())
        else:
            # Don't use the db
            self.ids[id] = server
            self.ids_date[id] = [datetime.datetime.utcnow()]

    def get_id(self, id):
        '''Get the server related with an id'''
        if self.lbdb:
            # Use the DB
            server_str = self.lbdb.get_rb_id(id)
            if server_str:
                server = LBServer(serial=server_str)
            else:
                server = None
        else:
            # Use the memory
            try:
                server = self.ids[id]
                self.ids_date[id].append(datetime.datetime.utcnow())
            except KeyError:
                server = None

        return server



class LBRoundRobin(LBInterface):
    '''LB class that implements Round Robin for Web Runner RESP API'''

    def __init__(self, servers, db=None):
        LBInterface.__init__(self, 'RoundRobin', servers, db)

        self.counter = 0

    def get_new_server(self, request):

        if not self.servers:
            return None

        ret_server = self.servers[self.counter]
        self.counter += 1

        if self.counter >= len(self.servers):
            self.counter = 0
        
        return ret_server

        
        


if __name__ == '__main__':
    servers = [LBServer('127.0.0.1', 65431),
        LBServer('127.0.0.1', 65432),
        LBServer('127.0.0.1', 65433),
        LBServer('127.0.0.1', None),
        ]

    lb = getLB(LB_ROUND_ROBIN, servers= servers)
    for index in range(10):
        serv = lb.get_new_server(None)
        print("server%d: %s:%s" % (index, serv.host, serv.port))
        print("Seting server %s:%s as id=%d" % (serv.host, serv.port, index))
        lb.set_id(index, serv)
    
    for index in range(11):
        serv = lb.get_id(index)
        if serv :
            print("Server for id=%d is %s:%s" % (index, serv.host, serv.port))
        else:
            print("No Server for id=%d " % (index))

# vim: set expandtab ts=4 sw=4:
