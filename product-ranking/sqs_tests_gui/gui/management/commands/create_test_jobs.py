# Creates many test jobs

import os
import random
import datetime

from django.core.management.base import BaseCommand

CWD = os.path.dirname(os.path.abspath(__file__))

from gui.models import Job


def _create_job(i):
    search_terms = [
        'laptop',
        'water',
        'iphone',
        'galaxy tab',
        'dresses',
        'black shoes',
        'green shoes',
        'cokies',
        'harry potter',
        'nice',
        'red',
        'black',
    ]
    sites = ['amazon_products',
            'walmart_products',
            'topshop_products',
            'amazonca_products',
            'amazoncouk_products',
            'amazonde_products'
    ]
    Job.objects.create(
        name='bulk created task %s - %s' % (
            datetime.datetime.utcnow().strftime("%Y.%m.%d"), i),
        spider=random.choice(sites),
        search_term=random.choice(search_terms),
        quantity=random.randrange(50, 1000),
        task_id=random.randrange(100000, 900000),
        mode='no cache',
        branch_name=''
    )


class Command(BaseCommand):
    help = 'Creates many test jobs'

    def handle(self, *args, **options):
        # TODO: command-line args for num of jobs and branch name
        N = 170
        for i in xrange(N):
            _create_job(i)
