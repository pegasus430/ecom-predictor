# Creates many test jobs

import os
import random
import argparse
import datetime

from django.core.management.base import BaseCommand

CWD = os.path.dirname(os.path.abspath(__file__))

from gui.models import Job


def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Load jobs from file.')

    return parser.parse_args()


class Command(BaseCommand):
    help = 'Load jobs from file'

    def add_arguments(self, parser):
        # Positional arguments
        parser.add_argument('file', help="a file to load jobs from (1 URL per line)")
        parser.add_argument('spider', help="the name of the spider")
        parser.add_argument('branch', help="the name of the branch to run the scrapers at")

    def handle(self, *args, **options):
        for line in open(options['file'], 'r'):
            line = line.strip()
            if not line:
                continue
            Job.objects.create(
                name='jobs from file - spider %s, created at %s' % (
                    options['spider'],
                    datetime.datetime.utcnow().strftime("%Y.%m.%d")),
                spider=options['spider'],
                product_url=line,
                quantity=99,
                task_id=random.randrange(100000, 9000000),
                mode='no cache',
                branch_name=options['branch']
            )
