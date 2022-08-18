import os
import sys
import json
import zipfile
import json

from django.core.management.base import BaseCommand

CWD = os.path.dirname(os.path.abspath(__file__))
#sys.path.append(os.path.join(CWD, '..', '..', '..', '..'))

from gui.models import Job


sys.path.append(os.path.join(CWD,  '..', '..', '..', '..', '..',
                             'deploy', 'sqs_ranking_spiders'))
from test_sqs_flow import download_s3_file, AMAZON_BUCKET_NAME, unzip_file
from .update_jobs import download_s3_file, _unzip_local_file, rename_first_file_with_extension

LOCAL_AMAZON_LIST = os.path.join(CWD, '_amazon_listing.txt')


class Command(BaseCommand):
    help = 'Downloads .JL files for the jobs by regexp'

    def handle(self, *args, **options):
        # get the jobs by regexp
        matching = raw_input('Enter the partial jobs matching: ')

        # get random jobs
        jobs = Job.objects.filter(name__icontains=matching)
        if raw_input('Found %i jobs. Enter "yes" to proceed: ' % len(jobs)).lower() in ('y', 'yes'):
            # now prepare the list of all files containing the given spider name and test server name
            list_containing_criteria = []
            for s3_file in open(LOCAL_AMAZON_LIST):
                if jobs[0].spider.replace('_products', '') in s3_file:
                    if jobs[0].server_name.replace('_', '-') in s3_file:
                        if '.jl' in s3_file:
                            list_containing_criteria.append(s3_file)

            if not os.path.exists('/tmp/_downloaded_files'):
                os.makedirs('/tmp/_downloaded_files')
            with open('/tmp/_matching_files', 'w') as fh:
                fh.write(json.dumps(list_containing_criteria))

            for job in jobs:
                # find an appropriate job id
                job_filename_matcher = '--%s____' % job.task_id
                for f in list_containing_criteria:
                    if job_filename_matcher in f:
                        local_full_path = '/tmp/_downloaded_files/' + str(job.id) + '/'
                        if not os.path.exists(local_full_path):
                            os.makedirs(local_full_path)
                        local_full_path += 'data_file.zip'
                        key_fname = f.replace('>', '').replace('<', '').split(',', 1)[1]
                        try:
                            download_s3_file(AMAZON_BUCKET_NAME, key_fname.strip(),
                                             local_full_path)
                        except Exception, e:
                            print str(e), key_fname
                            print job.product_url, '-->'
                            import pdb; pdb.set_trace()
                            continue
                        _unzip_local_file(local_full_path, 'data_file.jl', '.jl')
                        if zipfile.is_zipfile(local_full_path):
                            unzip_file(local_full_path,
                                       unzip_path=local_full_path)
                            os.remove(local_full_path)
                            rename_first_file_with_extension(
                                os.path.dirname(local_full_path),
                                'data_file.jl',
                                '.jl'
                            )
                        print job.product_url, '-->', local_full_path
                        with open(os.path.dirname(local_full_path) + '/data_file.jl') as fh:
                            cont = fh.read()
                        if not cont.strip():
                            with open('/tmp/jl_files_results.jl', 'a') as fh:
                                fh.write(json.dumps({'given_url': job.product_url})+'\n')
                        else:
                            try:
                                cont = json.loads(cont[0].strip())
                            except:
                                cont = json.loads(cont.strip())
                            with open('/tmp/jl_files_results.jl', 'a') as fh:
                                cont.update({'given_url': job.product_url})
                                fh.write(json.dumps(cont)+'\n')
