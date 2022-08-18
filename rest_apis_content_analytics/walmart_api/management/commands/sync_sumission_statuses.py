import json

from django.core.management import BaseCommand
from django.contrib.auth.models import User
from datetime import datetime

from statistics.models import SubmitXMLItem
from walmart_api.models import SubmissionResults


class Command(BaseCommand):
    help = (
        'Sync submission status for separate item from response json to SubmitXmlItem records.'
        '\n'
        'If SubmitXmlItem not existed for feed_id+upc it will be skipped'
    )

    def handle(self, *args, **options):
        total_results = SubmissionResults.objects.all().count()
        random_user = User.objects.first()
        auth = 'session'
        processed = 0
        print 'Submission results count: {}'.format(total_results)
        for result_item in SubmissionResults.objects.all():
            try:
                try:
                    result = json.loads(result_item.response)
                except Exception as e:
                    print 'response parsing error: \n{}'.format(e.message)
                    continue

                feed_id = result_item.feed_id
                result_items = result.get('itemDetails', {}).get('itemIngestionStatus', [])
                submitted_at = result.get('submitted_at', datetime.now())
                items_received = result.get('itemsReceived', 0)

                for json_item in result_items:
                    upc = json_item.get('sku')
                    status = json_item.get('ingestionStatus', '')
                    errors = (json_item.get('ingestionErrors') or {}).get('ingestionError', [])
                    errors_txt = (
                        '; '.join(
                            [
                                '"{}" ({})'.format(
                                    e.get('code', 'no code'),
                                    e.get('description', 'no description')
                                )
                                for e in errors
                            ]
                        )
                    )

                    if status.lower() == 'success':
                        status = SubmitXMLItem.STATUS_SUCCESS
                    else:
                        status = SubmitXMLItem.STATUS_FAILED
                    try:
                        db_item = SubmitXMLItem.objects.get(item_metadata__feed_id=feed_id, item_metadata__upc=upc)
                        if status != db_item.status:
                            msg = 'Wrong status found (at json "{0}", at db item "{1}") for feed_id="{2}", upc="{3}"'
                            print msg.format(status, db_item.status, feed_id, upc)
                            db_item.status = status
                            db_item.error_text = errors_txt
                            db_item.save()
                    except SubmitXMLItem.DoesNotExist:
                        print 'Item not found for feed_id = {0}, upc={1}'.format(feed_id, upc)
                        print 'Creating item with random user'
                        db_item = SubmitXMLItem.objects.create(
                            user=random_user,
                            auth=auth,
                            when=submitted_at,
                            status=status,
                            multi_item=bool(items_received > 1)
                        )
                        if errors_txt:
                            db_item.error_text = errors_txt
                        if upc and feed_id:
                            db_item.metadata = {'upc': upc, 'feed_id': feed_id}

                processed += 1
                print '{} results processed from {}'.format(processed, total_results)
            except Exception as e:
                print 'unhandled exception: {}'.format(e.message)
                print 'Result record is: {}'.format(result_item)
                print 'Sync for those items skipped'
