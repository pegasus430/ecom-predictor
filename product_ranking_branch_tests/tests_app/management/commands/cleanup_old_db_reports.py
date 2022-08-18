from django.core.management import BaseCommand
from tests_app.models import Report
import datetime


N_DAYS = 7


class Command(BaseCommand):
    def handle(self, *args, **options):
        date = datetime.datetime.now() - datetime.timedelta(days=N_DAYS)
        query = Report.objects.filter(when_created__lte=date)
        num_of_records = query.count()
        query.delete()
        print 'Deleted %s records' % num_of_records