# Sends daily reports about missing (or not missing) data.
# The goal is to only monitor if a spider stopped to return results.

import sys
import os
import datetime

from django.core.management.base import BaseCommand
from django.core.mail import send_mail

from boto import ses

CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(1, os.path.join(CWD, '..', '..', '..'))

os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

import settings
from tests_app.models import (Spider, TestRun, FailedRequest, Alert,
                              ThresholdSettings)


class Command(BaseCommand):
    can_import_settings = True

    def _num_of_active_spiders(self):
        return Spider.objects.filter(active=True).count()

    def handle(self, *args, **options):
        # send a summary email
        email_subj = '[%s] SC Auto-tests: data daily summary updates'
        global_failed = False
        spiders_status = {}
        for spider in Spider.objects.filter(active=True):
            if spider.get_failed_test_runs_for_24_hours_with_missing_data(
                    threshold=4):
                global_failed = True
                spiders_status[spider.name] = 'failed'
            else:
                spiders_status[spider.name] = 'passed'

        email_template = """
%i spider(s) checked. %i Failed. %i Passed.

Detailed Results (tests passed / total):

"""  % (len(spiders_status.keys()),
        len([s for s in spiders_status.items() if s[1] == 'failed']),
        len([s for s in spiders_status.items() if s[1] == 'passed']))

        for spider_name, spider_status in spiders_status.items():
            spider = Spider.objects.get(name=spider_name)
            _total_tr = spider.get_total_test_runs_for_24_hours().count()
            _failed_tr = spider.get_failed_test_runs_for_24_hours_with_missing_data(
                threshold=4).count()
            _passed_tr = _total_tr - _failed_tr
            if spider_status == 'failed':
                email_template += "* [FAILED] - %i/%i - %s." % (
                    _passed_tr, _total_tr, spider.name)
            else:
                email_template += "* [PASSED] - %i/%i - %s." % (
                    _passed_tr, _total_tr, spider.name)

            email_template += " Details: %s" % spider.get_absolute_url()
            email_template += '\n\n'

        email_subj %= 'PASSED' if not global_failed else 'FAILED'
        email_subj += ", UTC time: %s" % datetime.datetime.utcnow()

        # send report email
        conn = ses.connect_to_region(
            'us-east-1',
            aws_access_key_id=settings.AMAZON_SES_KEY,
            aws_secret_access_key=settings.AMAZON_SES_SECRET,
        )
        to_email = ThresholdSettings.objects.all().first()
        if to_email:
            to_email = to_email.notify
            to_email = [e.strip() for e in to_email.split(',')]
            print "SENDING TO", to_email
            print conn.send_email(
                'contentanalyticsinc.autotests@gmail.com',
                email_subj,
                email_template,
                to_addresses=to_email,
                bcc_addresses=[]
            )
