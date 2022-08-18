import os
import sys
import datetime
import json
import re
import ast
import subprocess
import random

from django.core.management.base import BaseCommand
from django.utils.timezone import now

CWD = os.path.dirname(os.path.abspath(__file__))
#sys.path.append(os.path.join(CWD, '..', '..', '..', '..'))

from settings import MEDIA_ROOT
from watchdog.models import WatchDogJob, WatchDogJobTestRuns
from gui.models import Job, get_log_filename
from gui.management.commands.update_jobs import _unzip_local_file


sys.path.append(os.path.join(CWD,  '..', '..', '..', '..', '..',
                             'deploy', 'sqs_ranking_spiders'))
from test_sqs_flow import download_s3_file,\
    AMAZON_BUCKET_NAME as AMAZON_BUCKET_NAME_OUTPUT_FILES


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


def _get_s3_output_key_from_log(log_file):
    """ Parses the log file and returns the appropriate S3 key for the output .JL file """
    with open(log_file, 'r') as fh:
        for line in fh:
            overriden_settings = re.search(
                "INFO: Overridden settings: (.*?)\n", line)
            if overriden_settings:
                overriden_settings = ast.literal_eval(overriden_settings.group(1).strip())
                server_fname = overriden_settings['FEED_URI'].rsplit('/', 1)[1]
                server_fname_date = datetime.datetime.strptime(
                    server_fname.split('____')[0], '%d-%m-%Y')
                return server_fname_date.strftime('%Y/%m/%d') + '/' + server_fname + '.zip'


def _get_data_file_from_bucket(data_file):
    server_fname = _get_s3_output_key_from_log()



class Command(BaseCommand):
    help = 'Runs a watchdog job and checks if it fails'

    def handle(self, *args, **options):
        if num_of_running_instances('watchdog_run_jobs') > 1:
            print 'an instance of the script is already running...'
            sys.exit()

        from jsonpath_rw import parse as jsonparse

        # get all active jobs
        active_jobs = [j for j in WatchDogJob.objects.all() if j.is_active()]
        for active_job in active_jobs:
            print("Creating test jobs for WatchDogJob #" + str(active_job.pk))
            for url in [u.strip() for u in active_job.urls.split('\n') if u.strip()]:
                spider_job = Job.objects.create(
                    name='WatchDog Job #%i' % active_job.pk,
                    spider=active_job.spider,
                    product_url=url,
                    task_id=random.randint(999999, 99999999),
                    branch_name=active_job.branch if active_job.branch else '',
                    search_term='', product_urls='', extra_cmd_args='',
                    mode='no cache')
                screenshot_job = Job.objects.create(
                    name='WatchDog Job #%i' % active_job.pk,
                    spider='url2screenshot_products',
                    product_url=url,
                    task_id=random.randint(999999, 99999999),
                    search_term='', product_urls='', extra_cmd_args='',
                    branch_name='',
                    mode='no cache')
                wd_test_run = WatchDogJobTestRuns.objects.create(
                    wd_job=active_job,
                    spider_job=spider_job,
                    screenshot_job=screenshot_job)
                print('    created test run %i' % wd_test_run.pk)

        # check all finished jobs with just created WatchDogJobTestRuns
        jobs = Job.objects.filter(status='finished', name__icontains="WatchDog Job")\
            .exclude(spider='url2screenshot_products')\
            .filter(wd_test_run_jobs__status='created').distinct()
        # get only active jobs
        _exclude_jobs = []
        for j in jobs:
            wd_job = j.wd_test_run_jobs.all()[0].wd_job
            if not wd_job.is_active():
                _exclude_jobs.append(j.pk)
        jobs = jobs.exclude(pk__in=_exclude_jobs).distinct()
        for job in jobs:
            wd_job = job.wd_test_run_jobs.all()[0].wd_job
            wd_job.last_checked = now()
            wd_job.save()

            wd_test_run = WatchDogJobTestRuns.objects.get(spider_job=job)
            wd_test_run.status = 'finished'
            wd_test_run.finished = now()
            wd_test_run.save()

            print('Checking results of SQS Job %i' % job.pk)

            job_log_file = MEDIA_ROOT + get_log_filename(job)
            s3_key_output_file = _get_s3_output_key_from_log(job_log_file)
            tmp_output_fname_zip = '/tmp/_tmp_output_fname.zip'
            tmp_output_fname = '/tmp/_tmp_output_fname.jl'
            download_s3_file(AMAZON_BUCKET_NAME_OUTPUT_FILES, s3_key_output_file,
                             tmp_output_fname_zip)
            _unzip_local_file(tmp_output_fname_zip, tmp_output_fname, '.jl')

            with open(tmp_output_fname, 'r') as fh:
                job_results = fh.read().strip()
            if job_results:
                job_results = json.loads(job_results)
            else:
                print('    error: empty results for SQS Job %i' % job.pk)
                continue

            result_value = [
                match.value
                for match in jsonparse(wd_job.response_path).find(job_results)]
            if str(result_value) != str(wd_job.desired_value):
                if result_value:
                    if str(result_value[0]) != str(wd_job.desired_value):
                        print('    error: values differ for WD Job %i' % job.pk)
                        wd_job.status = 'failed'
                        if not wd_test_run in list(wd_job.failed_test_runs.all()):
                            wd_job.failed_test_runs.add(wd_test_run)
                        wd_job.save()
                        wd_test_run.status = 'failed'
                        wd_test_run.save()
                        continue
            print('    ok: values are the same for WD Job %i' % job.pk)
