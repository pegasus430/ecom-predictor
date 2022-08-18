# Copyright (c) 2010  <copyright holders>
# 
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
# 
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


import sys
import re
from itertools import chain

from json import loads

from django.db import connection, transaction
from django.db.models import get_apps, get_models
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.core.management import color

HEADER = '# Django database dump'
HEADER_RE = re.compile('#\sDjango database dump')

qn = connection.ops.quote_name
dumps = DjangoJSONEncoder(ensure_ascii=False).encode

class DumpRestoreError(Exception):
    pass


class RestoreError(DumpRestoreError):
    pass


DISABLE_FOREIGN_KEYS_SQL = {
    'django.db.backends.sqlite3': None,
    'django.db.backends.mysql': 'SET foreign_key_checks = 0',
    'django.db.backends.postgresql_psycopg2': 'SET CONSTRAINTS ALL DEFERRED',
}


class EndOfDump(Exception):
    pass


class CleverIterator(object):
    def __init__(self, seq):
        self.iterator = iter(seq)
        try:
            self.first = next(self.iterator)
            self.empty = False
        except StopIteration:
            self.empty = True

    def __getitem__(self, index):
        if self.empty:
            raise IndexError
        if index != 0:
            raise NotImplementedError
        return self.first

    def __nonzero__(self):
        return not self.empty

    def __iter__(self):
        if self.empty:
            raise StopIteration
        yield self.first
        for item in self.iterator:
            yield item
        self.empty = True

    def next(self):
        return iter(self).next()


def get_all_models():
    """ Get all models, grouped by apps. """
    for app in get_apps():
        for model in get_models(app, include_auto_created=True):
            yield model


def server_side_cursor(connection):
    if not connection.connection:
        connection.cursor() # initialize DB connection

    backend = connection.settings_dict['ENGINE']
    if backend == 'django.db.backends.postgresql_psycopg2':
        # postgres named cursors require a transaction so we need to turn off autocommit if we're not in a transaction
        if (connection.connection.get_transaction_status() == 0):  #psycopg2.extensions.TRANSACTION_STATUS_IDLE
            connection.connection.autocommit = False
        cursor = connection.connection.cursor(name='dump')
        cursor.tzinfo_factory = None
        return cursor
    elif backend == 'django.db.backends.mysql':
        from MySQLdb.cursors import SSCursor
        return connection.connection.cursor(SSCursor)
    else:
        return connection.cursor()


def dump_table(table, fields, pk, converters):
    cursor = server_side_cursor(connection)
    qn = connection.ops.quote_name
    fields_sql = ', '.join(qn(field) for field in fields)
    table_sql = qn(table)
    pk_sql = qn(pk)
    yield '# %s' % dumps((table, fields))
    cursor.execute('SELECT %s FROM %s ORDER BY %s' % (fields_sql, table_sql, pk_sql))
    for row in cursor:
        yield dumps([converter(value, connection=connection) for converter, value in zip(converters, row)])
    yield ''
    cursor.close()


def dump_model(model):
    table = model._meta.db_table
    fields = [field.column for field in model._meta.local_fields]
    converters = [field.get_db_prep_value for field in model._meta.local_fields]
    pk = model._meta.pk.column
    return dump_table(table, fields, pk, converters)


def dump_all():
    return chain(*(dump_model(model) for model in get_all_models()))


def dump(file=sys.stdout):
    file.write(HEADER + '\n\n')
    for line in dump_all():
        file.write(line.encode('UTF-8') + '\n')


# http://code.djangoproject.com/ticket/9964
#@transaction.commit_on_success
def load(file=sys.stdin):
    """ Load data from file into the DB. """
    try:
        with transaction.atomic():
            disable_foreign_keys()
            for table, fields, rows in parse_file(file):
                load_table(table, fields, rows)

            reset_sequences()
    except:
        transaction.rollback()
        raise
    else:
        transaction.commit()


def parse_file(lines):
    """ Return a sequence of (table_name, fields, data_rows) for each dumped table. """
    find_main_header(lines)

    while True:
        header = find_table_header(lines)
        if not header: #EOF
            break
        table, fields = header
        yield table, fields, read_table_rows(lines)


def find_main_header(lines):
    for line in lines:
        match = HEADER_RE.search(line)
        if match:
            return
    raise RestoreError('File header not found - not a valid database dump.')


def find_table_header(lines):
    """ Find table data header. """
    for line in lines:
        if line.startswith('#'):
            header = line.lstrip('#')
            table, fields = loads(header)
            return table, fields


def read_table_rows(lines):
    """ Read table rows, stop at EOF or a blank line. """
    for line in lines:
        if not line or line.isspace():
            break
        else:
            yield loads(line)


def load_table(table, fields, rows):
    """ Load data into the given table with the given fields. """
    truncate_table(table)
    table_sql = qn(table)
    fields_sql = ', '.join(qn(field) for field in fields)
    params_sql = ', '.join('%s' for field in fields)
    insert_sql = 'INSERT INTO %s (%s) VALUES (%s)' % (table_sql, fields_sql, params_sql)
    executemany(insert_sql, rows)


def executemany(sql, rows):
    cursor = connection.cursor()
    for row in rows:
        cursor.execute(sql, row)


def truncate_table(table):
    """ Delete all rows from the given table. """
    cursor = connection.cursor()
    cursor.execute('DELETE FROM %s' % qn(table))


def disable_foreign_keys():
    """ Disable foreign key constraint checks using DB-specific SQL. """
    sql = DISABLE_FOREIGN_KEYS_SQL[connection.settings_dict['ENGINE']]
    if sql:
        cursor = connection.cursor()
        cursor.execute(sql)


def reset_sequences():
    """ Reset DB sequences, if needed. """
    models = get_all_models()
    sequence_reset_sql = connection.ops.sequence_reset_sql(color.no_style(), models)
    if sequence_reset_sql:
        cursor = connection.cursor()
        for line in sequence_reset_sql:
            cursor.execute(line)
