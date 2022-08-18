from __future__ import unicode_literals

from django.db import models


class Users(models.Model):
    username = models.CharField(max_length=100, unique=True)
    email = models.CharField(max_length=100)
    created_on = models.BigIntegerField()
    active = models.NullBooleanField()
    first_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50, blank=True, null=True)
    company = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    access_key = models.CharField(max_length=50, blank=True, null=True)
    secret_key = models.CharField(max_length=50, blank=True, null=True)
    timezone = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __unicode__(self):
        return self.username
