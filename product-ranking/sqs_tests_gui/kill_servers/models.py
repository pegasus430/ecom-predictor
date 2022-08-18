import datetime

from django.db import models
from django.contrib.auth.models import User


class ProductionBranchUpdate(models.Model):
    branch_to_track = 'sc_production'

    when_updated = models.DateTimeField(default=datetime.datetime.utcnow)

    last_commit_hashsum = models.CharField(max_length=100, blank=True, null=True)

    def __unicode__(self):
        return str(self.when_updated)

    class Meta:
        ordering = ('-when_updated', )


class ServerKill(models.Model):
    branch_update = models.ForeignKey(
        ProductionBranchUpdate, blank=True, null=True)
    manual_restart_by = models.ForeignKey(
        User, blank=True, null=True)
    started = models.DateTimeField(default=datetime.datetime.utcnow)
    finished = models.DateTimeField(blank=True, null=True)

    def __unicode__(self):
        return str(self.started)
