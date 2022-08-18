from __future__ import unicode_literals

from django.db import models
from walmart_api.models import SubmissionHistory

class MockedXMLStatus(models.Model):
    feed_id = models.CharField(max_length=50)
    current_status = models.CharField(max_length=50)
    in_progress = models.IntegerField()
    success = models.IntegerField()
    errors = models.IntegerField()
    data_error = models.IntegerField()
    timeout_error = models.IntegerField()