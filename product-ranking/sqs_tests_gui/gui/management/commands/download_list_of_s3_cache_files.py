import os
import sys
import subprocess
import tempfile

from django.core.management.base import BaseCommand


CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(CWD,  '..', '..'))
sys.path.append(os.path.join(CWD,  '..', '..', '..', '..', '..',
                             'deploy', 'sqs_ranking_spiders'))
from product_ranking.extensions import bucket_name
from list_all_files_in_s3_bucket import list_files_in_bucket


LOCAL_AMAZON_LIST_CACHE = os.path.join(CWD, '_amazon_cache_listing.txt')


def run(command, shell=None):
    """ Run the given command and return its output
    """
    out_stream = subprocess.PIPE
    err_stream = subprocess.PIPE

    if shell is not None:
        p = subprocess.Popen(command, shell=True, stdout=out_stream,
                             stderr=err_stream, executable=shell)
    else:
        p = subprocess.Popen(command, shell=True, stdout=out_stream,
                             stderr=err_stream)
    (stdout, stderr) = p.communicate()

    return stdout, stderr


def list_amazon_bucket(bucket=bucket_name,
                       local_fname=LOCAL_AMAZON_LIST_CACHE):
    filez = list_files_in_bucket(bucket)
    # dump to a temporary file and replace the original one then
    tmp_file = tempfile.NamedTemporaryFile(mode='rb', delete=False)
    tmp_file.close()

    with open(tmp_file.name, 'w') as fh:
        for f in filez:
            fh.write(str(f)+'\n')
    if os.path.exists(local_fname):
        os.unlink(local_fname)
    os.rename(tmp_file.name, local_fname)


def num_of_running_instances(file_path):
    """ Check how many instances of the given file are running """
    processes = 0
    output = run('ps aux')
    output = ' '.join(output)
    for line in output.split('\n'):
        line = line.strip()
        line = line.decode('utf-8')
        if file_path in line and not '/bin/sh' in line:
            processes += 1
    return processes


class Command(BaseCommand):
    help = 'Downloads the list of keys in S3 cache'

    def handle(self, *args, **options):
        if num_of_running_instances('download_list_of_s3_cache_files') > 1:
            print 'an instance of the script is already running...'
            sys.exit()

        list_amazon_bucket()
