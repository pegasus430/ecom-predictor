#!/usr/bin/env python
import logging
import sqlite3
import os
import datetime
import json

LOG = logging.getLogger(__name__)

COMMAND = 'command'
SPIDER = 'spider'
SPIDER_STATUS = 'spider_status'
COMMAND_STATUS = 'command_status'
SPIDER_RESULT = 'spider_result'
COMMAND_RESULT = 'command_result'

class DbInterface(object):
    """Class to handle requests persistency

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

        return sqlite3.connect(filename)


    def create_dbstructure(self):
        """Create the DB structure

        Returns a boolean with the operation success"""
        
        table1 = '''CREATE TABLE IF NOT EXISTS requests(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name VARCHAR,
          type VARCHAR,
          group_name VARCHAR,
          site VARCHAR,
          params TEXT,
          creation TIMESTAMP,
          remote_ip VARCHAR,
          details VARCHAR
          )'''

        table2 = '''CREATE TABLE IF NOT EXISTS scrapy_jobs(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          request_id INTEGER,
          scrapy_jobid VARCHAR,
          FOREIGN KEY(request_id) REFERENCES requests(id) 
            ON DELETE CASCADE 
            ON UPDATE CASCADE
          )'''

        table3 = '''CREATE TABLE IF NOT EXISTS request_ops(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          request_id INTEGER,
          date TIMESTAMP,
          type VARCHAR,
          description TEXT,
          FOREIGN KEY(request_id) REFERENCES requests(id) 
            ON DELETE CASCADE 
            ON UPDATE CASCADE
          );
          '''


        try:
            cursor = self._conn.cursor()
            cursor.execute(table1)
            cursor.execute(table2)
            cursor.execute(table3)
            self._conn.commit()
            cursor.close()
            ret = True
        except sqlite3.Error as e:
            LOG.error("Error creating the DB tables. Detail=" + str(e))
            ret = False

        return ret


    def _new_request(self, name, command_type, params, jobids, ip=None, id=None):
        """Add a new request to the DB:

        Input parameters:
          * name: name of the command or scraper
          * command_type: valid values are COMMAND or SPIDER
          * params: request params
          * jobids: list of scrapyd job associated to the command/spider

        Return: boolean with the operation success
        """
        
        DbInterface._counter += 1
        if not jobids:
            jobids = []
        params_json = json.dumps(params)
        group_name = params.get('group_name')
        site =  params.get('site')
        creation = datetime.datetime.utcnow()
        details = {'id': id} if id else {} 
        details_json = json.dumps(details)
        

        # Insert the main request
        insert_sql = '''INSERT INTO requests(name, type, group_name, site, 
          params, creation, remote_ip, details) values(?,?,?,?,?,?,?,?)'''
        sql_values= (name, command_type, group_name, site, params_json, 
          creation, ip, details_json)

        try:        
            cursor = self._conn.cursor()
            cursor.execute(insert_sql, sql_values)
            ret = True
        except sqlite3.Error as e:
            LOG.error("Error inserting a new request. Detail= " + str(e))
            ret = False

        if ret:
            # Add the scrapyd jobids
            request_id = cursor.lastrowid
            jobid_db_rows = [(request_id, jobid) for jobid in jobids]
            insert_jobids = '''INSERT INTO scrapy_jobs(request_id, scrapy_jobid)
              values(?,?)'''
            try:
                if len(jobid_db_rows):
                    cursor.executemany(insert_jobids, jobid_db_rows)
                self._conn.commit()
            except sqlite3.Error as e:
                LOG.error("Error inserting a new request. Detail= " + str(e))
                ret = False

        return ret

    def new_request_event(self, event_type, jobids, ip=None):
        """Add a new request to the DB:

        Input parameters:
          * event_type: valid values are SPIDER_STATUS, COMMAND_STATUS,
              SPIDER_RESULT, COMMAND_RESULT
          * params: request params
          * jobids: list of scrapyd job associated to the command/spider

        Return: boolean with the operation success
        """
        if not jobids:
            return False

        event_date = datetime.datetime.utcnow()

        # Get the requestid associated.
        sql = 'SELECT request_id FROM scrapy_jobs WHERE scrapy_jobid=?'
        cursor = self._conn.cursor()
        cursor.execute(sql, (jobids[0],))
        row = cursor.fetchone()
        if row is None:
            return False

        (requestid,) = row

        # Insert the event in the DB
        insert_sql = '''INSERT INTO request_ops(request_id, 
                        date, type, description)
                        VALUES(?,?,?,?)'''

        desc = json.dumps({'ip': ip}) if ip else ''
        sql_values = (requestid, event_date, event_type, desc)

        try:        
            cursor = self._conn.cursor()
            cursor.execute(insert_sql, sql_values)
            self._conn.commit()
            ret = True
        except sqlite3.Error as e:
            LOG.error("Error inserting an request event. Detail= %s", e)
            self._conn.rollback()
            ret = False

        return ret

    def new_spider(self, name, params, jobid, ip=None, id=None):
        """Insert a new spider into the DB

        Input parameters:
          * name: name of the spider
          * params: request params
          * jobid: scrapyd jobid associated 

        Return: boolean with the operation success
        """
        jobids = [jobid] if jobid else None
        return self._new_request(name, SPIDER, params, jobids, ip, id)


    def new_command(self, name, params, jobids, ip=None, id=None):
        """Add a new command to the DB:

        Input parameters:
          * name: name of the command 
          * params: request params
          * jobids: list of scrapyd job associated to the command

        Return: boolean with the operation success
        """
        return self._new_request(name, COMMAND, params, jobids, ip, id)

 
    def get_last_requests(self, size):
        """Returns the last 'size' requests within the DB

        The output is a list of dictionary, each one representing a request.
        The dict keys are:
          * name, type, group_name, site, params(type: json), creation
        """

        cursor = self._conn.cursor()
        sql = '''SELECT id, name, type, group_name, site, params, creation,
          remote_ip, details
          FROM requests 
          ORDER BY creation DESC 
          LIMIT %d''' % size;
        cursor.execute(sql)

        output = []
        for row in cursor.fetchall():
            (id, name, type, group_name, site, params, creation, ip,
              details) = row
            row_dict = {
              'requestid': id,
              'name': name,
              'type': type,
              'group_name': group_name,
              'site': site,
              'params': params,
              'creation': creation,
              'remote_ip': ip,
              'jobids': self._get_jobids(id),
              'details': details }
            output.append(row_dict)
        
        return output


    def get_request(self, requestid):
        """Returns information about the requestid

        The output is a dictionary whose keys are:
          * name, type, group_name, site, params(type: json), creation
        """

        cursor = self._conn.cursor()
        sql = '''SELECT id, name, type, group_name, site, params, creation,
          remote_ip 
          FROM requests 
          WHERE id=? '''
        cursor.execute(sql, (requestid,))

        row = cursor.fetchone()
        row_dict = None
        if row:
            (id, name, type, group_name, site, params, creation, ip) = row
            row_dict = {
              'requestid': id,
              'name': name,
              'type': type,
              'group_name': group_name,
              'site': site,
              'params': params,
              'creation': creation,
              'remote_ip': ip,
              'jobids': self._get_jobids(id) }
        
        return row_dict


    def get_req_operations(self, requestid):
        """
        Load all request operations (status and result)

        The function returns a list of tuple. The tuple position will have:
          0: date
          1: operation type (SPIDER_STATUS, COMMAND_STATUS, SPIDER_RESULT or
                             COMMAND_RESULT)
          2: ip
        """
        
        cursor = self._conn.cursor()
        sql = '''SELECT date, type, description
          FROM request_ops
          WHERE request_id = ? '''
        cursor.execute(sql, (requestid,))

        ret = []
        for row in cursor.fetchall():
            (date,  type, desc) = row

            # Parse the IP if it exists
            try:
                ip = json.loads(desc)['ip']
            except ValueError:
                ip = ''

            ret.append((date, type, ip))
        cursor.close()

        return ret


    def get_requestid(self, jobids):
        """Return a tuple with all requestid associate to jobids"""

        cursor = self._conn.cursor()
    
        # Create the query
        #sql = 'SELECT DISTINCT request_id FROM scrapy_jobs WHERE scrapy_jobid in (?)'
        #quote_gen = map((lambda x: "'" + x + "'"), jobids)
        #jobids_sql = '(' + ','.join(quote_gen) + ')'
        #cursor.execute(sql, (jobids_sql,))

        # Create the query
        # WARNING: This query is insecure. I was not able to do it 
        # in a secure way. For sure it is possible. Needs to be updated.
        quote_gen = map((lambda x: "'" + x + "'"), jobids)
        jobids_sql = ','.join(quote_gen)
        sql = '''
            SELECT DISTINCT request_id 
            FROM scrapy_jobs 
            WHERE scrapy_jobid in (%s)''' % jobids_sql
        cursor.execute(sql)

        output = tuple( request_id[0] for request_id in cursor.fetchall() or () )

        return output

    def _get_jobids(self, request_id):
        """Return a tuple with all jobids asociated to a request id"""
        
        cursor = self._conn.cursor()
        sql = 'SELECT scrapy_jobid FROM scrapy_jobs where request_id=?'
        cursor.execute(sql, (request_id,))
        output = tuple( jobid[0] for jobid in cursor.fetchall() or () )

        return output
        

if __name__ == '__main__':
    dbinterf = DbInterface('/tmp/web_runner.db', recreate=False)

    params = { "group_name": 'gabo_test', 
        "searchterms_str": "laundry detergent", 
        "site": "walmart", 
        "quantity": "100"}
    #dbinterf.new_command('gabo name', params, None)
    last_reqs = dbinterf.get_last_requests(2)
    print(last_reqs)
    dbinterf.close()
    

# vim: set expandtab ts=4 sw=4:
