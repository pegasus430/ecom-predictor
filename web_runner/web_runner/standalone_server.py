#
# This is a workaround for the awful scrapyd server
#

import os
import sys
import bz2


from flask import Flask, redirect
app = Flask(__name__)


REDIRECT_PATTERN = '/crawl/project/product_ranking/spider/<string:spider_name>/job/<string:job_id>/'
REDIRECT_URL = '/result/project/product_ranking/spider/{spider_name}/job/{job_id}/'
RESULT_PATTERN = '/result/project/product_ranking/spider/<string:spider_name>/job/<string:job_id>/'
DATA_FILE_PATH = '/home/web_runner/virtual-environments/scrapyd/items/product_ranking/{spider_name}/{job_id}.jl'


def file_is_bzip2(fname):
    """ Tests if the given file is bzipped """
    if not os.path.exists(fname):
        return
    fh = bz2.BZ2File(fname)
    try:
        _ = fh.next()
        fh.close()
        return True
    except Exception, e:
        fh.close()
        return False


def unbzip(f1, f2):
    try:
        f = bz2.BZ2File(f1)
        cont = f.read()
    except:
        return False
    f.close()
    with open(f2, 'wb') as fh:
        fh.write(cont)
    return True


def is_plain_json_list(fname):
    with open(fname, 'r') as fh:
        cont = fh.read(1024)
    cont = cont.strip()
    if not cont:
        return True
    return cont[0] == '{'


def fix_double_bzip_in_file(fname):
    if not is_plain_json_list(fname):
        print 'File [%s] compressed, decompressing...' % fname
        result1 = unbzip(fname, fname)
        while result1:
            result1 = unbzip(fname, fname)
            print '  RECURSIVE BZIP DETECTED', fname


@app.route(REDIRECT_PATTERN)
def redirect_view(spider_name, job_id):
    return redirect(
        REDIRECT_URL.format(spider_name=spider_name, job_id=job_id),
        code=302
    )


@app.route(RESULT_PATTERN)
def result_view(spider_name, job_id):
    local_fname = DATA_FILE_PATH.format(spider_name=spider_name, job_id=job_id)
    fix_double_bzip_in_file(local_fname)
    with open(local_fname, 'rb') as fh:
        content = fh.read()
    return content


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=9090)