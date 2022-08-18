import os
import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

CWD = os.path.dirname(os.path.abspath(__file__))

from gui.models import Job
from .delete_old_logs_and_data_files import get_old_dirs, MEDIA_ROOT,\
    REMOVE_FILES_OLDER_THAN


class Command(BaseCommand):
    help = 'Removes old jobs (older than REMOVE_FILES_OLDER_THAN)'

    def handle(self, *args, **options):
        dt = timezone.now() - datetime.timedelta(days=REMOVE_FILES_OLDER_THAN)
        old_jobs = Job.objects.filter(finished__lte=dt)

        for folder, modified_time in get_old_dirs(MEDIA_ROOT):
            os.system('rm -rf "%s"' % folder)
            print 'FOLDER [%s] REMOVED' % folder

        old_jobs.delete()
