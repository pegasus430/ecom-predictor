from __future__ import unicode_literals

from django.db import models
from api_auth.models import Users

# Create your models here.
class Query(models.Model):
    remote_address = models.CharField(max_length=32)
    user = models.ForeignKey(Users, on_delete=models.CASCADE, null=True)
    request_method = models.CharField(max_length=20)
    request_path = models.CharField(max_length=400)
    request_body = models.TextField(blank=True, null=True)
    response_status = models.IntegerField()
    date = models.DateTimeField(auto_now_add=True)
    run_time = models.FloatField()

    class Meta:
        db_table = 'api_insights_log'