# Turns many 'grouper' objects into single Job.
# In other words, turns many "product_url" into "product_urls" batches

import os
import json
import random

MAX_URLS = 15  # how many URLs to group into a single batch

from django.core.management.base import BaseCommand

CWD = os.path.dirname(os.path.abspath(__file__))

from gui.models import Job, JobGrouperCache


class Command(BaseCommand):
    help = 'Turns many grouper objects into single Job'

    def handle(self, *args, **options):
        all_sites = JobGrouperCache.objects.all().only('spider')
        all_sites = list(set([s.spider for s in all_sites]))  # make unique
        for site in all_sites:
            # get all groupers OLDER than the last N_MINS minutes
            groupers = JobGrouperCache.objects.filter(spider=site)\
                           .order_by('?')[0:MAX_URLS]
            if not groupers:
                continue

            print
            print site
            for g in groupers:
                print ' '*4, 'adding URL:', g.product_url

            # turn them into a single batch
            multiurl = '||||'.join([g.product_url.strip() for g in groupers])
            extra_args = json.loads(groupers[0].extra_args)

            Job.objects.get_or_create(
                name=extra_args['name'],
                spider=site,
                search_term='',
                product_urls=multiurl,
                quantity=200,
                task_id=random.randrange(100000, 900000),
                mode='no cache',
                save_raw_pages=True,
                branch_name=extra_args['branch_name']
            )

            [g.delete() for g in groupers]   # we don't need them anymore
