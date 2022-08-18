#
# Removes old (>3 days) cache dirs and DB records.
# Also removes old code dirs (which may not have been deleted because of
# failed test run execution)
#


import sys
import os
import datetime
import shutil

from django.core.management.base import BaseCommand
from django.utils.timezone import now

CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(1, os.path.join(CWD, '..', '..', '..'))

os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

from tests_app.models import LocalCache

N_DAYS = 3


def modification_date(path):
    t = os.path.getmtime(path)
    return datetime.datetime.fromtimestamp(t)


def _get_old_dirs_and_files(base_dir):
    if '~' in base_dir:
        base_dir = os.path.expanduser(base_dir)
    for d in os.listdir(base_dir):
        full_dir = os.path.join(base_dir, d)
        dir_mtime = modification_date(full_dir)
        if dir_mtime < datetime.datetime.now() - datetime.timedelta(days=N_DAYS):
            yield full_dir


class Command(BaseCommand):
    can_import_settings = True

    def handle(self, *args, **options):
        # clear DB records
        LocalCache.objects.filter(
            when_created__lte=now()-datetime.timedelta(days=N_DAYS)
        ).delete()
        # clear cache dirs
        for d in _get_old_dirs_and_files(base_dir='~/_sc_tests_cache/'):
            if os.path.isdir(d):
                shutil.rmtree(d)
        # clear repo dirs
        for d in _get_old_dirs_and_files(base_dir='~/_test_runs/'):
            if os.path.isdir(d):
                shutil.rmtree(d)