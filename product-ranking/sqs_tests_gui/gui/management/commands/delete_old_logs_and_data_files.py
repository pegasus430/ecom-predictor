import os
import time

from django.core.management.base import BaseCommand

CWD = os.path.dirname(os.path.abspath(__file__))

from settings import MEDIA_ROOT, REMOVE_FILES_OLDER_THAN


def get_old_dirs(dir_path, older_than=REMOVE_FILES_OLDER_THAN*60*60*24):
    time_now = time.time()
    for path, folders, files in os.walk(dir_path):
        for folder in folders:
            folder_path = os.path.join(path, folder)
            modified_time = time_now - os.path.getmtime(folder_path)
            if modified_time > older_than:
                yield folder_path, modified_time


class Command(BaseCommand):
    help = 'Clear files older than REMOVE_FILES_OLDER_THAN days (settings.py)'

    def handle(self, *args, **options):
        for folder, modified_time in get_old_dirs(MEDIA_ROOT):
            os.system('rm -rf "%s"' % folder)
            print 'FOLDER [%s] REMOVED' % folder
