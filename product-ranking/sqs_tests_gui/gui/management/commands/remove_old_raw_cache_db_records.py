import os
import datetime
import sys

from django.core.management.base import BaseCommand

CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(CWD, '..', '..', '..', '..', 'product_ranking'))

from cache_models import Run


def remove_db_records(max_days=14):
    """ Get cache data, spider -> date -> searchterm
    supports strings for spider (as name) and for terms(as term)
    :return: dict
    """
    global session
    query = session.query(Run)
    query = query.filter(Run.date <= datetime.datetime.now()-datetime.timedelta(days=max_days))
    for run in query:
        print('Removing Run[%s]' % run.id)
        session.query(Run).filter_by(id=run.id).delete()
    session.commit()


class Command(BaseCommand):
    help = 'Removes old Raw Cache DB records (older than 14 days)'

    def handle(self, *args, **options):
        remove_db_records()
