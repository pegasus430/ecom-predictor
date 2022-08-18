import datetime

from django.db import models
from django.utils import timezone

from gui.models import Job


class WatchDogJob(models.Model):
    _statuses = ['ok', 'failed']

    name = models.CharField(help_text="Any name, for convenience", blank=True, null=True, max_length=100)

    created = models.DateTimeField(auto_now_add=True)
    last_checked = models.DateTimeField(blank=True, null=True)
    run_for_days = models.IntegerField(default=5, help_text="Num of days the job should be active for")

    spider = models.CharField(max_length=100, help_text='Like walmart_products or amazon_products')

    urls = models.TextField(help_text="List of URLs to look the desired values in, 1 per line")

    desired_value = models.CharField(help_text="Any value will be converted using str()", max_length=150)
    response_path = models.CharField(
        help_text="JsonPath in the output file, see"
                  " https://github.com/masukomi/jsonpath-perl/tree/master"
                  " for syntax help",
        max_length=200)

    branch = models.CharField(help_text="Leave blank for sc_production", blank=True, null=True, max_length=100)

    status = models.CharField(max_length=50, choices=[(s, s) for s in _statuses], default='ok')

    failed_test_runs = models.ManyToManyField('WatchDogJobTestRuns', blank=True)

    def is_active(self):
        return timezone.now() < self.created + datetime.timedelta(days=self.run_for_days)

    def __unicode__(self):
        return u'WatchDogJob %i, status: %s' % (self.pk, self.status)


class WatchDogJobTestRuns(models.Model):
    wd_job = models.ForeignKey(WatchDogJob)

    created = models.DateTimeField(auto_now_add=True)
    finished = models.DateTimeField(blank=True, null=True)

    spider_job = models.ForeignKey(Job, related_name="wd_test_run_jobs")
    screenshot_job = models.ForeignKey(Job)

    status = models.CharField(max_length=100, choices=Job._status_choices,
                              default='created')

    def __unicode__(self):
        return u'TestRun %i, job %s' % (self.pk, self.wd_job)
