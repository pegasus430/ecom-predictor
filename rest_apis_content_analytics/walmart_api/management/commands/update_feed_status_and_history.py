import os
import sys
import subprocess

from django.core.management import BaseCommand
from django.contrib.auth.models import User

from walmart_api.models import *
from walmart_api.views import (parse_walmart_api_log, get_walmart_api_invoke_log,
                               get_feed_status, CheckFeedStatusByWalmartApiViewSet)
from walmart_api.context_processors import get_submission_history_as_json
from statistics.models import *
from statistics.context_processors import stats_walmart_xml_items


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


def check_running_instances(marker):
    """ Check how many processes with such marker are running already"""
    processes = 0
    output = run('ps aux')
    output = ' '.join(output)
    for line in output.split('\n'):
        line = line.strip()
        line = line.decode('utf-8')
        if marker in line and not '/bin/sh' in line:
            processes += 1
    return processes


class Command(BaseCommand):
    help = 'Updates feed history and statistics for all users'

    @staticmethod
    def exit_if_multiple_instances_running():
        basename = os.path.basename(__file__).replace('.pyc', '').replace('.py', '')
        if check_running_instances(basename) > 1:
            print('Multiple instances of this script are running - exit')
            sys.exit(-1)

    def handle(self, *args, **options):

        self.exit_if_multiple_instances_running()

        for user in User.objects.all():
            records = list(parse_walmart_api_log(user))
            records.reverse()
            for log_rec in records:  # TODO: parse server name and IP
                date = log_rec['datetime']
                upc = log_rec['upc'].strip()
                feed_id = log_rec['feed_id'].strip()
                server_name = log_rec.get('server_name', None)
                client_ip = log_rec.get('client_ip', None)
                print 'Feed ID %s' % feed_id

                # check feed response from walmart
                response = None
                check_feed_view = CheckFeedStatusByWalmartApiViewSet()
                try:
                    response = check_feed_view.process_one_set(  # this will get the feed ID from DB or will get live response
                        'https://marketplace.walmartapis.com/v2/feeds/{feedId}?includeDetails=true',
                        feed_id,
                        user
                    )
                except Exception as e:
                    print str(e)
                    continue

                # update old "incomplete" statuses - remove SubmissionHistory records and Statistics
                for sub_history in SubmissionHistory.objects.filter(
                        user=user, feed_id=feed_id):
                    if not sub_history.all_items_ok():
                        _statuses = [s.lower() for s in sub_history.get_statuses()]
                        if 'received' in _statuses or 'inprogress' in _statuses:
                            print 'REFRESHING STATUS %s' % feed_id, _statuses
                            print 'Removing existing SubmissionHistory and Statistics for feed ID %s' % feed_id
                            SubmissionHistory.objects.filter(user=user, feed_id=feed_id).delete()
                            SubmitXMLItem.objects.filter(user=user, item_metadata__feed_id=feed_id).delete()
                            continue
                # process feed statuses for unprocessed items
                print get_feed_status(user, feed_id, date=date,
                                      process_check_feed=True, check_auth=False,
                                      server_name=server_name, client_ip=client_ip)

            # this will regenerate cache
            get_submission_history_as_json(user, delete_old_cache=True, generate_cache=True)
            stats_walmart_xml_items(user, delete_old_cache=True, generate_cache=True)