# TODO: bestsellers check

import os
import sys
import datetime
import json
import zipfile
import subprocess
import tempfile

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils.timezone import now
import boto
from dateutil.parser import parse as parse_date

CWD = os.path.dirname(os.path.abspath(__file__))
#sys.path.append(os.path.join(CWD, '..', '..', '..', '..'))

from settings import MEDIA_ROOT
from gui.models import Job, get_data_filename, get_log_filename,\
    get_progress_filename


sys.path.append(os.path.join(CWD,  '..', '..', '..', '..', '..',
                             'deploy', 'sqs_ranking_spiders'))
import scrapy_daemon
from test_sqs_flow import download_s3_file, AMAZON_BUCKET_NAME, unzip_file
from list_all_files_in_s3_bucket import list_files_in_bucket

LOCAL_AMAZON_LIST = os.path.join(CWD, '_amazon_listing.txt')


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


def list_amazon_bucket(bucket=AMAZON_BUCKET_NAME,
                       local_fname=LOCAL_AMAZON_LIST,
                       date=datetime.datetime.now()):
    filez = list_files_in_bucket(bucket,
                                 prefix=date.strftime('%Y/%m/%d/'),
                                 delimiter='/')
    # dump to a temporary file and replace the original one then
    tmp_file = tempfile.NamedTemporaryFile(mode='rb', delete=False)
    tmp_file.close()

    with open(tmp_file.name, 'w') as fh:
        for f in filez:
            fh.write(str(f)+'\n')
    if os.path.exists(local_fname):
        os.unlink(local_fname)
    os.rename(tmp_file.name, local_fname)
    os.chmod(local_fname, 0777)


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


def rename_first_file_with_extension(base_dir, new_fname, extension='.csv'):
    for filename in os.listdir(base_dir):
        if filename.lower().endswith(extension):
            os.rename(
                os.path.join(base_dir, filename),
                os.path.join(base_dir, new_fname)
            )
            return


def _unzip_local_file(fname, new_fname, ext):
    if zipfile.is_zipfile(fname):
        unzip_file(fname, unzip_path=fname)
        os.remove(fname)
        rename_first_file_with_extension(
            os.path.dirname(fname),
            new_fname,
            ext
        )


def _get_output_queue_name_for_job(job):
    return job.server_name + scrapy_daemon.OUTPUT_QUEUE_NAME


def _get_progress_queue_name_for_job(job):
    return job.server_name + scrapy_daemon.PROGRESS_QUEUE_NAME


def _get_server_name_from_queue(queue_name):
    return queue_name.replace(scrapy_daemon.OUTPUT_QUEUE_NAME, '')\
        .replace(scrapy_daemon.PROGRESS_QUEUE_NAME, '')


def get_output_queues_for_jobs(jobs):
    """ Returns unique SQS queues names for the given jobs """
    queues = []
    for j in jobs:
        q_name = _get_output_queue_name_for_job(j)
        if not q_name in queues:
            queues.append(q_name)
    return list(set(queues))


def _get_queue(queue_name, region="us-east-1"):
    conn = boto.sqs.connect_to_region(region)
    return conn.get_queue(queue_name)


def read_messages_from_queue(queue_name, region="us-east-1", timeout=5, num_messages=5555):
    q = _get_queue(queue_name, region=region)
    if q:
        num_iterations = num_messages / 10 + 1
        result = []
        for i in range(0, num_iterations):
            for m in q.get_messages(num_messages=10, visibility_timeout=timeout):
                result.append(m)
        return result
    return []


def _delete_queue_message(queue_or_name, msg, region="us-east-1"):
    if isinstance(queue_or_name, (str, unicode)):
        queue_or_name = _get_queue(queue_or_name, region=region)
    queue_or_name.delete_message(msg)


def get_progress_queues_for_jobs(jobs):
    """ Returns unique SQS queues names for the given jobs """
    queues = []
    for j in jobs:
        q_name = _get_progress_queue_name_for_job(j)
        if not q_name in queues:
            queues.append(q_name)
    return list(set(queues))


class Command(BaseCommand):
    help = 'Updates 50 random jobs taken from the output queues,' \
           ' downloading their files if ready'

    def handle(self, *args, **options):
        if num_of_running_instances('update_jobs') > 1:
            print 'an instance of the script is already running...'
            sys.exit()
        # Deprecated, uncomment if needed
        # list_amazon_bucket()  # list files for /search-files/ site page

        # get random jobs
        jobs = Job.objects.filter(
            Q(status='pushed into sqs') | Q(status='in progress')
        ).order_by('?').distinct()[0:300]

        # get output & progress queue names
        output_queues = get_output_queues_for_jobs(jobs)
        progress_queues = get_progress_queues_for_jobs(jobs)

        for progress_queue in progress_queues:
            progress_messages = read_messages_from_queue(progress_queue)
            for m in progress_messages:
                m_body = m.get_body()
                if isinstance(m_body, (str, unicode)):
                    m_body = json.loads(m_body)
                task_id = m_body.get('task_id', m_body.get('_msg_id', None))
                # remove messages that are way too old
                utc_datetime = m_body.get('utc_datetime', None)
                if utc_datetime:
                    utc_datetime = parse_date(utc_datetime)
                    if utc_datetime < datetime.datetime.now() - datetime.timedelta(days=1):
                        _delete_queue_message(progress_queue, m)
                        print('Deleted old message: %s' % str(m_body))
                        continue
                if task_id is None:
                    continue
                server_name = _get_server_name_from_queue(progress_queue)
                # get the appropriate DB job
                db_job = Job.objects.filter(
                    Q(status='pushed into sqs') | Q(status='in progress'),
                    task_id=task_id, server_name=server_name)
                if db_job.count() > 1:
                    print 'Too many jobs found for message'
                    import pprint
                    pprint.pprint(m_body)
                    print '=Jobs:='
                    pprint.pprint(db_job)
                    continue
                if not db_job:
                    continue  # not found in DB?
                db_job = db_job[0]

                # ok now we've got a message in the queue and its appropriate DB job
                # create progress file
                full_local_prog_path = MEDIA_ROOT + get_progress_filename(db_job)
                if not os.path.exists(os.path.dirname(full_local_prog_path)):
                    os.makedirs(os.path.dirname(full_local_prog_path))
                with open(full_local_prog_path, 'w') as fh:
                    fh.write(json.dumps(m_body))
                progress = m_body.get('progress', None)
                if progress not in (None, 'finished'):
                    db_job.status = 'in progress'
                    db_job.save()
                    _delete_queue_message(progress_queue, m)
                    print('Deleted progress message: %s' % str(m_body))
                if progress == 'failed':
                    print("DB Job %s reported as failed (in progress message)" % db_job.pk)
                    db_job.status = 'failed'
                    db_job.save()
                    _delete_queue_message(progress_queue, m)
                    print('Deleted progress message: %s' % str(m_body))
                print('Downloaded progress file to %s' % full_local_prog_path)

        # scan output queue (read the messages)
        for output_queue in output_queues:
            output_messages = read_messages_from_queue(output_queue)
            for m in output_messages:
                m_body = m.get_body()
                if isinstance(m_body, (str, unicode)):
                    m_body = json.loads(m_body)
                print "output message body"
                import pprint
                pprint.pprint(m_body)
                task_id = m_body.get('task_id', m_body.get('_msg_id', None))


                #This is new
                if not task_id:
                    task_id = m_body.get('msg_id')


                # remove messages that are way too old
                utc_datetime = m_body.get('utc_datetime', None)
                if utc_datetime:
                    utc_datetime = parse_date(utc_datetime)
                    if utc_datetime < datetime.datetime.now() - datetime.timedelta(days=3):
                        _delete_queue_message(output_queue, m)
                        print('Deleted old message: %s' % str(m_body))
                        continue
                if task_id is None:
                    continue
                server_name = _get_server_name_from_queue(output_queue)
                # get the appropriate DB job
                db_job = Job.objects.filter(
                    Q(status='pushed into sqs') | Q(status='in progress'),
                    task_id=task_id, server_name=server_name)
                if db_job.count() > 1:
                    print 'Too many jobs found for message %s' % str(m_body)
                    print db_job
                    continue
                if not db_job:
                    continue  # not found in DB?
                db_job = db_job[0]

                # ok now we've got a message in the queue and its appropriate DB job
                # now - save files
                amazon_data_file = m_body.get('csv_data_key', None)
                amazon_json_data_file = m_body.get('s3_key_data', None) or m_body.get('s3_filepath', None)
                amazon_log_file = m_body.get('s3_key_logs', None)

                if m_body.get('status') == "failure":
                    db_job.status = 'failed'
                    db_job.save()
                    continue

                print
                print '=' * 79
                print 'Processing JOB'
                import pprint
                pprint.pprint(db_job.__dict__)
                print 'Data file', amazon_data_file
                print 'Log file', amazon_log_file

                if amazon_log_file:
                    full_local_log_path = MEDIA_ROOT + get_log_filename(db_job)
                    if not os.path.exists(os.path.dirname(full_local_log_path)):
                        os.makedirs(os.path.dirname(full_local_log_path))
                    download_s3_file(AMAZON_BUCKET_NAME, amazon_log_file,
                                     full_local_log_path)
                    _unzip_local_file(full_local_log_path, 'log.log', 'log')
                    with open(full_local_log_path, 'r') as fh:
                        cont = fh.read()
                        if not "'finish_reason': 'finished'" in cont:
                            if not "INFO: Closing spider (finished)" in cont:
                                print('Successful job ending is not found for job %s' % db_job.pk)
                                db_job.status = 'failed'
                                db_job.save()
                                continue

                if amazon_data_file:
                    print 'For job with task ID %s we found amazon fname [%s]' % (
                        db_job.task_id, amazon_data_file)

                    full_local_data_path = MEDIA_ROOT + get_data_filename(db_job)
                    if not os.path.exists(os.path.dirname(full_local_data_path)):
                        os.makedirs(os.path.dirname(full_local_data_path))
                    download_s3_file(AMAZON_BUCKET_NAME, amazon_data_file,
                                     full_local_data_path)
                    _unzip_local_file(full_local_data_path, 'data_file.csv', '.csv')
                    if zipfile.is_zipfile(full_local_data_path):
                        unzip_file(full_local_data_path,
                                   unzip_path=full_local_data_path)
                        os.remove(full_local_data_path)
                        rename_first_file_with_extension(
                            os.path.dirname(full_local_data_path),
                            'data_file.csv',
                            '.csv'
                        )

                if not amazon_data_file and amazon_json_data_file:  # CSV conversion failed? OR new architecture
                    print 'For job with task ID %s we found amazon fname [%s]' % (
                        db_job.task_id, amazon_json_data_file)
                    full_local_data_path = MEDIA_ROOT + get_data_filename(db_job)
                    print "local path"
                    print full_local_data_path
                    if not os.path.exists(os.path.dirname(full_local_data_path)):
                        os.makedirs(os.path.dirname(full_local_data_path))
                    bucket_from_msg = m_body.get('bucket_name')
                    # Done when path to bucket is strange
                    # if not amazon_data_file[0] == "/":
                    #     amazon_data_file = "/{}".format(amazon_data_file)
                    if bucket_from_msg:
                        download_s3_file(bucket_from_msg, amazon_json_data_file,
                                         full_local_data_path)
                    else:
                        download_s3_file(AMAZON_BUCKET_NAME, amazon_json_data_file,
                                     full_local_data_path)
                    print "donwloaded data file at"
                    print full_local_data_path
                    # No need to unzip, new architecture - download as is

                    _unzip_local_file(full_local_data_path, 'data_file.csv', '.jl')
                    if zipfile.is_zipfile(full_local_data_path):
                        unzip_file(full_local_data_path,
                                   unzip_path=full_local_data_path)
                        os.remove(full_local_data_path)
                        rename_first_file_with_extension(
                            os.path.dirname(full_local_data_path),
                            'data_file.jl',
                            '.jl'
                        )

                if amazon_data_file or amazon_json_data_file:
                    # old and new arch criteria
                    if amazon_log_file or m_body.get('status') == "success":

                        db_job.status = 'finished'
                        db_job.finished = now()
                        db_job.save()
                        _delete_queue_message(output_queue, m)
                        print('Deleted successful message: %s' % str(m_body))
