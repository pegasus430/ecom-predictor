import os
import sys
import datetime

from django.db import models
from django.utils.timezone import now

from jsonfield import JSONField  # pip install jsonfield
from multiselectfield import MultiSelectField
from slugify import slugify

CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(CWD, '..', '..', '..', '..'))
from utils import get_sc_fields, generate_spider_choices


DEFAULT_EXCLUDE_FIELDS = [
    '_statistics'
]


class SearchTerm(models.Model):
    searchterm = models.CharField(max_length=100)
    quantity = models.IntegerField(default=300)

    def __unicode__(self):
        return u'%s [%s]' % (self.searchterm, self.quantity)


class Spider(models.Model):
    name = models.CharField(
        max_length=100, unique=True, choices=generate_spider_choices())
    searchterms = models.ManyToManyField(SearchTerm, help_text="Choose at least 3.")

    def __unicode__(self):
        return self.name


class TestRun(models.Model):
    _status_choices = ('stopped', 'running', 'passed', 'failed')

    when_started = models.DateTimeField(auto_now_add=True)
    when_finished = models.DateTimeField(blank=True, null=True)

    branch1 = models.CharField(
        max_length=150,
        help_text=("A valid branch to compare with"
                   " (normally, master or sc_production)"))
    branch2 = models.CharField(max_length=150)

    spider = models.ForeignKey(Spider, related_name='spider_test_runs')
    status = models.CharField(
        choices=[(c, c) for c in _status_choices], max_length=20,
        default='stopped'
    )

    exclude_fields = MultiSelectField(
        choices=[(k,k) for k in sorted(get_sc_fields())],
        null=True, blank=True,
        default=DEFAULT_EXCLUDE_FIELDS)
    exclude_duplicates = models.BooleanField(
        help_text='Exclude duplicated products', default=False)
    skip_urls = models.CharField(
        max_length=150, blank=True, null=True,
        help_text="All URLs containing this pattern will be skipped")
    strip_get_args = models.BooleanField(default=False)

    def __unicode__(self):
        return 'Branches [%s - %s], Spider [%s], started %s, %s' % (
            self.branch1, self.branch2, self.spider.name, self.when_started,
            self.status.upper())


class Report(models.Model):
    when_created = models.DateTimeField(auto_now_add=True)
    testrun = models.ForeignKey(TestRun, related_name="testrun_reports")

    def not_enough_matched_urls(self):
        for searchterm in self.report_searchterms.all():
            if searchterm.not_enough_matched_urls():
                return True

    def diffs_found(self):
        for searchterm in self.report_searchterms.all():
            if searchterm.diffs:
                return True

    def __unicode__(self):
        return 'Test run %s' % (self.testrun.__unicode__().lower())


class ReportSearchterm(models.Model):
    report = models.ForeignKey(Report, related_name="report_searchterms")
    searchterm = models.ForeignKey(SearchTerm, related_name="searchterm_reports")

    total_urls = models.IntegerField(blank=True, null=True, help_text="Do not fill")
    matched_urls = models.IntegerField(blank=True, null=True, help_text="Do not fill")
    diffs = JSONField(blank=True, null=True, help_text="Do not fill")

    when_created = models.DateTimeField(auto_now_add=True)

    def not_enough_matched_urls(self):
        """ Returns True if the number of matched URLs is too low
            (so the report is not precise enough)
        """
        if self.total_urls is not None and self.matched_urls is not None:
            if not self.total_urls:
                return True  # zero?
            percent = (float(self.matched_urls) / float(self.total_urls)) * 100
            if int(percent) < 85:
                return True
        if self.matched_urls == 0:
            return True
        if self.matched_urls and self.matched_urls < 10:
            return True

    def __unicode__(self):
        return '[%s] [%s]' % (self.report.__unicode__().lower(),
                              self.searchterm.__unicode__())


class LocalCache(models.Model):
    searchterm = models.ForeignKey(SearchTerm)
    test_run = models.ForeignKey(TestRun)
    spider = models.ForeignKey(Spider)
    when_created = models.DateTimeField(auto_now_add=True)

    def is_valid(self, max_hours=12):
        if not self.when_created:
            return
        if (now() - self.when_created).total_seconds() / 60 / 60 > max_hours:
            return False
        return True

    def get_cache_identifier(self):
        _st = self.searchterm.searchterm
        _quantity = self.searchterm.quantity
        if isinstance(_st, unicode):
            _st = _st.encode('utf8')
        _spider = self.spider.name
        return (_spider + '__' + slugify(_st) + '__' + str(_quantity)
                + '__' + str(self.test_run.pk))

    def get_path(self, base_path='~/_sc_tests_cache/'):
        base_path = os.path.expanduser(base_path)
        return os.path.join(base_path, self.get_cache_identifier())

    def __unicode__(self):
        return '%s - %s - %s' % (self.searchterm, self.spider, self.when_created)
