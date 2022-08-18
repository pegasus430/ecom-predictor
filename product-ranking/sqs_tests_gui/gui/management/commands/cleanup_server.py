# Run from superuser!

import os
import datetime
import shutil

from django.core.management.base import BaseCommand


OLDER_THAN = 1  # days

PATTERNS = {
    '/tmp/pip-': None,  # None to match any size; or size in Megabytes
    '/tmp/tmp': 768,
}


def modification_date(filename):
    t = os.path.getmtime(filename)
    return datetime.datetime.fromtimestamp(t)


class Command(BaseCommand):
    help = 'Performs server cleanup (/tmp/ folder mostly)'

    def handle(self, *args, **options):
        for obj in os.listdir('/tmp/'):
            fname = os.path.join('/tmp/', obj)
            if not os.path.exists(fname):
                continue
            for pattern_name, pattern_size in PATTERNS.items():
                if pattern_name in fname:
                    if modification_date(fname) < datetime.datetime.now() - datetime.timedelta(days=OLDER_THAN):
                        size = os.path.getsize(fname) / 1024 / 1024
                        if (pattern_size and size > pattern_size) or pattern_size is None:
                            if os.path.isdir(fname):
                                shutil.rmtree(fname)
                            else:
                                os.unlink(fname)
                            print 'Removed: %s' % fname
