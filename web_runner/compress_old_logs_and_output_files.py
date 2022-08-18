#
# Scrapy logs and output files (.jl) take too much HDD space.
# Lets compress the old ones (older than N days).
# We will preserve the old extension, because Scrapyd would fail
# to remove the files since it uses unsafe os.remove() call
# (see scrapyd/environ.py)
#

import os
import sys


CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(1, os.path.join(CWD, 'web_runner'))
from util import (find_files, file_age_in_seconds, file_is_bzip2,
                  num_of_running_instances)


if num_of_running_instances(__file__) > 1:
    sys.exit()


# TODO: parse configs and get paths from there
PATH_PREFIX = '/home/web_runner/virtual-environments'
if not os.path.exists(PATH_PREFIX):
    PATH_PREFIX = '/root/virtual-environments'  # Digital Ocean test server

ITEMS_DIR = os.path.join(PATH_PREFIX, 'scrapyd/items/product_ranking')
LOGS_DIR = os.path.join(PATH_PREFIX, 'scrapyd/logs/product_ranking')
N_DAYS = 2


def is_plain_json_list(fname):
    if not os.path.exists(fname):
        return -1
    with open(fname, 'r') as fh:
        cont = fh.read(1024)
    cont = cont.strip()
    if not cont:
        return True
    return cont[0] == '{'


def compress_and_rename_old(fname):
    if file_is_bzip2(fname):
        return  # compressed already
    if not is_plain_json_list(fname):
        return  # compressed already
    if is_plain_json_list(fname) == -1:
        return  # file does not exist?
    if file_age_in_seconds(fname) < N_DAYS*86400:
        return  # not old
    os.system('bzip2 "%s"' % fname)
    os.rename(fname+'.bz2', fname)
    print '  File compressed:', fname


if __name__ == '__main__':
    for output_file in find_files(ITEMS_DIR, '*.jl'):
        compress_and_rename_old(output_file)
    for log_file in find_files(LOGS_DIR, '*.log'):
        compress_and_rename_old(log_file)