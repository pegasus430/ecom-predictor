import os
import sys
import re

from django.core.management.base import BaseCommand

CWD = os.path.dirname(os.path.abspath(__file__))
#sys.path.append(os.path.join(CWD, '..', '..', '..', '..'))

from gui.models import Job


sys.path.append(os.path.join(CWD,  '..', '..', '..', '..', '..',
                             'deploy', 'sqs_ranking_spiders'))
from add_task_to_sqs import put_msg_to_sqs


class Command(BaseCommand):
    help = ('Takes up to 50 oldest newly created Jobs'
            ' and pushes them into the test SQS queue')

    def handle(self, *args, **options):
        jobs = Job.objects.filter(status='created').order_by(
            '?').distinct()[0:500]
        for job in jobs:
            msg = {
                'task_id': int(job.task_id),
                'site': job.spider.replace('_products', ''),
                'server_name': job.server_name,
                'cmd_args': {'quantity': job.quantity}
            }
            if not job.quantity:
                del msg['cmd_args']['quantity']
            if job.slack_username:
                msg['cmd_args']['slack_username'] = job.slack_username
            if job.save_raw_pages:
                msg['cmd_args']['save_raw_pages'] = '1'
            #elif job.load_raw_pages:
            #    msg['cmd_args']['load_raw_pages'] \
            #        = job.load_raw_pages.strftime('%Y-%m-%d')
            if not msg['cmd_args']:
                del msg['cmd_args']
            if job.search_term:
                msg['searchterms_str'] = job.search_term
            elif job.product_url:
                msg['url'] = job.product_url
            elif job.product_urls:
                msg['urls'] = job.product_urls
            if job.with_best_seller_ranking:
                msg['with_best_seller_ranking'] = True
            if job.branch_name:
                msg['branch_name'] = job.branch_name
            if job.extra_cmd_args and job.extra_cmd_args.strip():
                for _arg in job.extra_cmd_args.split('\n'):
                    if not _arg.strip():
                        continue  # skip empty lines
		    search =  re.findall('^(.*?)=(.*)$', _arg.strip())
                    if search:
                        extra_arg_name, extra_arg_value = search[0]
                        extra_arg_name = extra_arg_name.strip()
                        extra_arg_value = extra_arg_value.strip()
                    if not 'cmd_args' in msg:
                        msg['cmd_args'] = {}
                    msg['cmd_args'][extra_arg_name] = extra_arg_value
            if job.sc_ch_mode:
                msg['response_format'] = "ch"
            else:
                msg['response_format'] = "sc"

            msg['result_queue'] = "test_serversqs_ranking_spiders_output"

            put_msg_to_sqs(msg, job.get_input_queue())
            job.status = 'pushed into sqs'
            job.save()

            self.stdout.write('Job %i pushed into SQS' % job.pk)
