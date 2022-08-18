import datetime

from django.db import models
from django.db.models import Q
from django.core.urlresolvers import reverse_lazy
from django.utils import timezone

from settings import HOST_NAME, PORT


class ThresholdSettings(models.Model):
    """ When to send an alert """
    n_errors_in_row = models.IntegerField(
        help_text='Num of consecutive errors (failed test runs)'
                  ' before sending an alert'
    )
    percent_of_failed_requests = models.IntegerField(
        help_text='Percent of total failed requests before sending an alert')
    notify = models.CharField(
        max_length=400,
        help_text='Enter all recipients who will receive alerts'
                  ' (separate emails by comma)'
    )

    def __unicode__(self):
        return '{0} errors in a row; {1}% failed requests'.format(
            self.n_errors_in_row, self.percent_of_failed_requests)


class Spider(models.Model):
    name = models.CharField(max_length=100, unique=True,
                            help_text='Like walmart_products')
    threshold_settings = models.ForeignKey(ThresholdSettings)
    n_errors_in_row = models.IntegerField(
        blank=True, null=True,
        help_text=('Num of consecutive errors before sending an alert '
                   '(override global `threshold settings` if needed)')
    )
    percent_of_failed_requests = models.IntegerField(
        blank=True, null=True,
        help_text='Percent of total failed requests before sending an alert'
                  '(override global `threshold settings` if needed)')
    notify = models.CharField(
        max_length=400, blank=True, null=True,
        help_text=('Enter all recipients who will receive alerts'
                   ' (separate emails by comma) - you may override the global'
                   '`threshold settings` value')
    )
    active = models.BooleanField(
        default=True,
        help_text='Uncheck to disable checking of this spider')

    def __unicode__(self):
        return self.name

    def get_n_errors_in_row(self):
        return (self.n_errors_in_row if self.n_errors_in_row
                else self.threshold_settings.n_errors_in_row)

    def get_percent_of_failed_requests(self):
        return (self.percent_of_failed_requests
                if self.percent_of_failed_requests
                else self.threshold_settings.percent_of_failed_requests)

    def get_notify(self):
        return self.notify if self.notify else self.threshold_settings.notify

    def last_consecutive_errors(self):
        """ Returns a number showing the amount of the last check failures
            (occured in a row, consecutive)
        :return: int
        """
        max_objs = 99
        all_test_runs = self.spider_test_runs.order_by(
            '-when_finished')[0:max_objs]  # avoid extra DB requests
        if not all_test_runs:
            return
        if all_test_runs[0].status not in ('running', 'failed'):
            return  # the last test run passed or hasn't started at all
        if all_test_runs[0].status == 'running':
            # there may be a working check, ignore it
            all_test_runs = all_test_runs[1:]
        for i, tr in enumerate(all_test_runs):
            if tr.status != 'failed':
                return i

    def get_last_failed_test_run(self):
        return self.get_last_failed_test_runs().first()

    def get_last_failed_test_runs(self):
        return self.spider_test_runs.filter(status='failed')\
            .order_by('-when_finished')

    def get_last_successful_test_runs(self):
        return self.spider_test_runs.filter(status='passed')\
            .order_by('-when_finished')

    def get_last_running_test_runs(self):
        return self.spider_test_runs.filter(status='running')\
            .order_by('-when_finished')

    def get_test_runs(self):
        return self.spider_test_runs.order_by('-when_finished')

    def get_passed_test_runs_for_24_hours(self):
        hrs_24 = timezone.now() - datetime.timedelta(days=1)
        return self.spider_test_runs.filter(
            status='passed', when_finished__gte=hrs_24
        ).order_by('-when_finished').distinct()

    def get_failed_test_runs_for_24_hours(self):
        hrs_24 = timezone.now() - datetime.timedelta(days=1)
        return self.spider_test_runs.filter(
            status='failed', when_finished__gte=hrs_24
        ).order_by('-when_finished').distinct()

    def get_failed_test_runs_for_24_hours_with_missing_data(self, threshold=2):
        _exclude_ids = []
        frs = self.get_failed_test_runs_for_24_hours()
        for fr in frs:
            num_of_req_with_missing_data = fr.test_run_failed_requests.filter(
                Q(error__icontains='got 0 results')
                | Q(error__icontains='some products missing')
            ).distinct().count()
            num_of_req_total = fr.test_run_failed_requests.all().count()
            # TODO: calculate (by percent) if this test req actually failed or not
            if num_of_req_with_missing_data <= threshold:
                _exclude_ids.append(fr.pk)
        return frs.exclude(id__in=_exclude_ids).distinct()

    def get_total_test_runs_for_24_hours(self):
        hrs_24 = timezone.now() - datetime.timedelta(days=1)
        return self.spider_test_runs.filter(
            when_finished__gte=hrs_24
        ).order_by('-when_finished').distinct()

    def get_absolute_url(self):
        if int(PORT) != 80:
            _host = HOST_NAME + ':%s' % PORT
        else:
            _host = HOST_NAME
        return 'http://' + _host + str(reverse_lazy(
            'tests_app_spider_review', kwargs={'pk': self.pk}))

    def is_error(self):
        """ Returns True if the last test runs failed as many times
            as needed to send an alert
        """
        cons_errors = self.last_consecutive_errors()
        if not cons_errors:
            return False
        return cons_errors >= self.get_n_errors_in_row()


class TestRun(models.Model):
    _status_choices = ('stopped', 'running', 'passed', 'failed')

    when_started = models.DateTimeField(auto_now_add=True)
    when_finished = models.DateTimeField(blank=True, null=True)

    spider = models.ForeignKey(Spider, related_name='spider_test_runs')
    status = models.CharField(
        choices=[(c, c) for c in _status_choices], max_length=20,
        default='stopped'
    )

    num_of_failed_requests = models.IntegerField(
        default=0, help_text='Num of failed requests after testing')
    num_of_successful_requests = models.IntegerField(
        default=0, help_text='Num of successfull requests after testing')

    def get_last_alert(self):
        return self.test_run_alerts.all().order_by('-when_created').first()

    def __unicode__(self):
        return 'For [%s], started %s' % (self.spider.name, self.when_started)


class FailedRequest(models.Model):
    test_run = models.ForeignKey(
        TestRun, related_name='test_run_failed_requests')
    request = models.CharField(max_length=150)
    when_created = models.DateTimeField(auto_now_add=True)
    error = models.TextField(blank=True, null=True,
                             help_text='Found errors (if any)')
    error_html = models.TextField(blank=True, null=True,
                                  help_text='Found errors (in HTML format)')
    result_file = models.FileField(blank=True, null=True)
    log_file = models.FileField(blank=True, null=True)

    def is_missing_data(self):
        return 'got 0 results' in str(self.error)\
               or 'some products missing' in str(self.error)


class Alert(models.Model):
    """ Store list of sent alerts to avoid sending tons of emails """
    test_run = models.ForeignKey(TestRun, related_name='test_run_alerts')
    when_created = models.DateTimeField(auto_now_add=True,
                                        blank=True, null=True)
