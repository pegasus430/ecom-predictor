#!/usr/bin/env python
import logging
import sqlite3
import os
import datetime
import json

LOG = logging.getLogger(__name__)

class Lbdb(object):
    """Class to handle load balancing persistency

    It is implemented using sqlite3 backend
    """

    _counter = 0

    def __init__(self, filename, recreate=False):
        """Constructor

        * filename: where the DB will be store. Can be ':memory:' to store
          it on memory.
        * recreate: if True, erase all previous content
        """
        if recreate and filename.lower() != ':memory:':
            self._erase_file(filename)

        self.filename = filename
        self._recreate = recreate
        self._conn = self._open_dbconnection(filename)


    def close(self):
        """Close DB connection"""
        self._conn.close()


    def _erase_file(self, filename):
        """Erase a file ignoring if it does not exist"""

        try:
            os.remove(filename)
        except OSError:
            pass

        return


    def _open_dbconnection(self, filename):
        """Open a sqlite3 connection"""

        return sqlite3.connect(filename, check_same_thread=False)


    def create_dbstructure(self):
        """Create the DB structure

        Returns a boolean with the operation success"""
        
        table1 = '''CREATE TABLE IF NOT EXISTS round_robin(
          key TEXT PRIMARY KEY,
          value TEXT
          )'''

        try:
            cursor = self._conn.cursor()
            cursor.execute(table1)
            self._conn.commit()
            cursor.close()
            ret = True
        except sqlite3.Error as e:
            LOG.error("Error creating the DB tables. Detail=" + str(e))
            ret = False

        return ret


    def set_rb_id(self, id, value):
        '''Set a round robin id into the db'''
        sql = '''
            INSERT OR REPLACE INTO round_robin(key, value)
            VALUES (?, ?)
        '''
        sql_values = (id, value) 

        try:        
            cursor = self._conn.cursor()
            cursor.execute(sql, sql_values)
            self._conn.commit()
            ret = True
        except sqlite3.Error as e:
            LOG.error("Error inserting a round robin id. Detail= " + str(e))
            ret = False

        return ret
 
    def get_rb_id(self, id):
        '''Get a Round Robin value'''
        cursor = self._conn.cursor()
        sql = '''SELECT value 
          FROM round_robin 
          WHERE key=? '''
        cursor.execute(sql, (id,))

        row = cursor.fetchone()
        ret = row[0] if row else None
        
        return ret
       

        

if __name__ == '__main__':
    import pdb; pdb.set_trace()
    lbdb = Lbdb('/tmp/lb.db', recreate=False)
    lbdb.create_dbstructure()

    lbdb.set_rb_id(1, 'value for key 1')
    lbdb.set_rb_id('2', 'value for key2')
    key1 = lbdb.get_rb_id(1)
    key2 = lbdb.get_rb_id('2')
    key3 = lbdb.get_rb_id('333')

    lbdb.close()
    

# vim: set expandtab ts=4 sw=4:
