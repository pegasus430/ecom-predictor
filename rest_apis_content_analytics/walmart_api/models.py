import datetime

from django.db import models
from django.contrib.auth.models import User


class SubmissionHistory(models.Model):
    """ Tracks the history of items uploaded to Walmart """
    user = models.ForeignKey(User, blank=True, null=True, on_delete=models.SET_NULL)
    feed_id = models.CharField(max_length=50)
    server_name = models.CharField(max_length=100, blank=True, null=True)
    client_ip = models.CharField(blank=True, null=True, max_length=50)
    created = models.DateTimeField(auto_now_add=True, blank=True, null=True)

    def get_statuses(self):
        qs = SubmissionStatus.objects.filter(history__feed_id=self.feed_id, history__user=self.user)
        return [s.status for s in qs]

    def set_statuses(self, status_list):
        for status in status_list:
            SubmissionStatus.objects.create(history=self, status=status)

    def all_items_ok(self):
        return all([s.lower() == 'success' for s in self.get_statuses()])

    def partial_success(self):
        statuses = [s.lower() for s in self.get_statuses()]
        return 'success' in statuses and not self.all_items_ok()

    def in_progress(self):
        statuses = [s.lower() for s in self.get_statuses()]
        return 'inprogress' in statuses


class SubmissionStatus(models.Model):
    history = models.ForeignKey(SubmissionHistory)
    status = models.CharField(max_length=20, db_index=True)


class SubmissionXMLFile(models.Model):
    feed_id = models.CharField(max_length=50)
    xml_file = models.FileField(help_text="The actual XML file sent to Walmart")
    created = models.DateTimeField(default=datetime.datetime.utcnow)


class SubmissionResults(models.Model):
    """ The result of the Feed submission (full status text from Walmart) """
    feed_id = models.CharField(max_length=50)
    response = models.TextField()
    updated = models.DateTimeField(default=datetime.datetime.utcnow)

    def __unicode__(self):
        return self.feed_id


class RichMediaMarketingContent(models.Model):
    marketing_content = models.TextField()
