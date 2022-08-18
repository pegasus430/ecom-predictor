import datetime
import logging

from django.db import models
from django.contrib.auth.models import User


logger = logging.getLogger('default')


def process_check_feed_response(user, check_results_output, date, check_auth=True):
    if check_auth and not user.is_authenticated():
        return
    multi_item = not(check_results_output.get('itemsReceived', 0) == 1)
    ingestion_statuses = check_results_output.get('itemDetails', {}).get('itemIngestionStatus', [])
    feed_id = check_results_output.get('itemDetails', {}).get('feedId')
    if not feed_id:
        feed_id = check_results_output.get('feedId')

    for item in check_results_output.get('itemDetails', {}).get('itemIngestionStatus', []):
        if 'ingestionStatus' not in item:
            print('No ingestionStatus found!')
            continue

        if item['ingestionStatus'].lower() not in ('success', 'received'):
            stat_xml_item(
                user,
                'session',
                'failed',
                multi_item,
                date=date,
                error_text=str(item.get('ingestionErrors')),
                upc=item.get('sku'),
                feed_id=feed_id
            )
            print('Stat item created for feed %s, status: FAILED, UPC: %s' % (feed_id, item.get('sku')))
        else:
            stat_xml_item(
                user,
                'session',
                'successful',
                multi_item,
                date=date,
                upc=item.get('sku'),
                feed_id=feed_id
            )
            print('Stat item created for feed %s, status: SUCCESS, UPC: %s' % (feed_id, item.get('sku')))

    if not ingestion_statuses:
        if check_results_output.get('feedStatus', '').lower() == 'error':
            stat_xml_item(
                user,
                'session',
                'failed',
                multi_item,
                date=date,
                error_text=str(check_results_output.get('ingestionErrors')),
                upc=check_results_output.get('sku'),
                feed_id=feed_id
            )
            print('Stat item created for feed %s, status: FAILED, UPC: %s' % (feed_id, check_results_output.get('sku')))


def stat_xml_item(user, auth, status, multi_item, date, error_text=None, upc=None, feed_id=None):
    # check if item already present
    try:
        item = SubmitXMLItem.objects.get(item_metadata__feed_id=feed_id, item_metadata__upc=upc)
        # skip creation if it's already existed
        return item
    except SubmitXMLItem.DoesNotExist:
        pass

    item = SubmitXMLItem.objects.create(
        user=user, auth=auth, when=date, status=status, multi_item=multi_item
    )
    if error_text:
        item.error_text = error_text
    if upc and feed_id:
        item.metadata = {'upc': upc, 'feed_id': feed_id}
    return item


def sync_xml_item_statuses(results, feed_id, user):
    result_items = results.get('itemDetails', {}).get('itemIngestionStatus', [])
    submitted_at = results.get('submitted_at', datetime.datetime.now())
    items_received = results.get('items_received', 0)

    for json_item in result_items:
        upc = json_item.get('sku')
        status = json_item.get('ingestionStatus', '')
        if status.lower() == 'success':
            status = SubmitXMLItem.STATUS_SUCCESS
        else:
            status = SubmitXMLItem.STATUS_FAILED
        try:
            db_item = SubmitXMLItem.objects.get(item_metadata__feed_id=feed_id, item_metadata__upc=upc)
            if db_item.status != status:
                db_item.status = status
        except SubmitXMLItem.DoesNotExist:
            # item not existed yet skipping it
            logger.warning('Item not found for feed_id = {0}, upc={1}'.format(feed_id, upc))

            db_item = SubmitXMLItem.objects.create(
                user=user,
                auth='session',
                when=submitted_at,
                status=status,
                multi_item=bool(items_received > 1)
            )

            errors = (json_item.get('ingestionErrors') or {}).get('ingestionError', [])

            if errors:
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

                db_item.error_text = errors_txt

            if upc and feed_id:
                db_item.metadata = {'upc': upc, 'feed_id': feed_id}
        finally:
            db_item.save()


def _filter_qs_by_date(qs, field_name, date):
    args = {
        field_name+'__year': date.year,
        field_name+'__month': date.month,
        field_name+'__day': date.day
    }
    return qs.filter(**args)


class SubmitXMLItem(models.Model):
    STATUS_SUCCESS = 'successful'
    STATUS_FAILED = 'failed'
    _status = (
        STATUS_SUCCESS,
        STATUS_FAILED
    )
    _auth_types = (
        'session',  # user submit item via web site
        'basic'  # user used some code to submit item and used Basic authentication
    )

    user = models.ForeignKey(User)
    auth = models.CharField(max_length=15, choices=[(a, a) for a in _auth_types])
    status = models.CharField(max_length=20, choices=[(c, c) for c in _status])  # db_index=True)
    when = models.DateTimeField(default=datetime.datetime.now)  # db_index=True)
    multi_item = models.BooleanField(default=False)  # if multiple items have been merged into one

    def __unicode__(self):
        return u'%s, %s => %s' % (self.user, self.when, self.status)

    @property
    def metadata(self):
        item_metadata = ItemMetadata.objects.filter(item=self)
        if not item_metadata:
            return
        return item_metadata[0]

    @metadata.setter
    def metadata(self, upc_and_feed_id_dict):
        if self.metadata:
            return
        ItemMetadata.objects.create(
            item=self,
            upc=upc_and_feed_id_dict.get('upc', None),
            feed_id=upc_and_feed_id_dict.get('feed_id', None)
        )

    @property
    def error_text(self):
        item_text = ErrorText.objects.filter(item=self)
        if not item_text:
            return
        return item_text[0].text

    @error_text.setter
    def error_text(self, text):
        try:
            error = ErrorText.objects.get(item=self)
            error.text = text
            error.save()
        except ErrorText.DoesNotExist:
            ErrorText.objects.create(item=self, text=text)

    @classmethod
    def failed_xml_items(cls, request):
        return cls.objects.filter(user=request.user, status='failed').order_by('-when').distinct()

    @classmethod
    def successful_xml_items(cls, request):
        return cls.objects.filter(user=request.user, status='successful').order_by('-when').distinct()

    @classmethod
    def today_all_xml_items(cls, request):
        return _filter_qs_by_date(
            cls.objects.filter(user=request.user),
            'when', datetime.datetime.today()
        ).order_by('-when').distinct()

    @classmethod
    def today_successful_xml_items(cls, request):
        return _filter_qs_by_date(
            cls.objects.filter(user=request.user, status='successful'),
            'when',
            datetime.datetime.today()
        ).order_by('-when').distinct()


class ErrorText(models.Model):
    item = models.ForeignKey(SubmitXMLItem, unique=True)
    text = models.TextField(blank=True, null=True)

    def __unicode__(self):
        return u'[%s]' % self.item


class ItemMetadata(models.Model):
    item = models.ForeignKey(SubmitXMLItem, unique=True, related_name='item_metadata')
    upc = models.CharField(max_length=20, blank=True, null=True, db_index=True)
    feed_id = models.CharField(max_length=50, blank=True, null=True, db_index=True)

    def __unicode__(self):
        return u'[%s], upc=>%s, feed_id=>%s' % (self.item, self.upc, self.feed_id)
