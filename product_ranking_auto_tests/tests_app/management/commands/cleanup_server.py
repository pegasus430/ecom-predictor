# Will remove "media" files that are older than N days

import os
import sys
import datetime
import shutil

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


OLDER_THAN = 30  # days


class Command(BaseCommand):

    def handle(self, *args, **options):
        for spider in os.listdir(os.path.join(settings.MEDIA_ROOT, 'output')):
            for str_date in os.listdir(os.path.join(settings.MEDIA_ROOT, 'output', spider)):
                date = datetime.datetime.strptime(str_date, '%d_%m_%Y')
                if date < datetime.datetime.now() - datetime.timedelta(days=OLDER_THAN):
                    dir_path = os.path.join(settings.MEDIA_ROOT, 'output', spider, str_date)
                    print 'Removing', dir_path
                    shutil.rmtree(dir_path)
