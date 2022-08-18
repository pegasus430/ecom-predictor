"""
Merges downloaded output CSV files in one, for jobs filtered by given template
"""

import os
import sys
import csv
import copy

from django.core.management.base import BaseCommand
from django.conf import settings

CWD = os.path.dirname(os.path.abspath(__file__))
#sys.path.append(os.path.join(CWD, '..', '..', '..', '..'))

from gui.models import Job, get_data_filename


sys.path.append(os.path.join(CWD,  '..', '..', '..', '..', '..',
                             'deploy', 'sqs_ranking_spiders'))


class Command(BaseCommand):
    help = __doc__

    def handle(self, *args, **options):
        jobs_template = raw_input("Enter the name of the jobs to search for: ")

        # get random jobs
        jobs = Job.objects.filter(
            status='finished', name__icontains=jobs_template)

        confirm = raw_input("Found %i jobs, continue? Y/N: " % jobs.count())
        if confirm.lower() not in ('y', 'yes'):
            print('You did not confirm - exit')
            sys.exit(1)

        output_fname = raw_input("Enter output (merged) file name: ")
        if os.path.exists(output_fname):
            if raw_input("Output file %s already exists, overwrite? Y/N: ").lower()\
                    not in ('y', 'yes'):
                print("Will not overwrite - exit...")

        # collect all rows from all files of these jobs
        all_jobs_content = []
        for job_i, job in enumerate(jobs):
            if job_i % 500 == 0:
                print('  processed %i jobs so far' % job_i)
            job_output_fname = settings.MEDIA_ROOT + get_data_filename(job)
            with open(job_output_fname, 'r') as fh:
                reader = csv.reader(fh)  # delimiter=',', quotechar='"')
                file_dicts = copy.copy([])
                for i, row in enumerate(reader):
                    if i == 0:
                        headers = row
                    else:
                        row_dict = copy.copy({})
                        for col_i, field_value in enumerate(row):
                            row_dict[headers[col_i]] = field_value
                        row_dict['given_url'] = job.product_url
                        if '_statistics' in row_dict:
                            del row_dict['_statistics']
                        file_dicts.append(row_dict)
                all_jobs_content.append(file_dicts)

        # now find out all possible field names
        field_names = []
        for file_content in all_jobs_content:
            for row in file_content:
                for key in row.keys():
                    if key not in field_names:
                        field_names.append(key)

        with open(output_fname, 'wb') as csvfile:
            writer = csv.writer(csvfile, delimiter=',',
                                quotechar='"', quoting=csv.QUOTE_ALL)
            writer.writerow(field_names)
            for file_content in all_jobs_content:
                for row in file_content:
                    row2write = [row.get(_k, '') for _k in field_names]
                    writer.writerow(row2write)
