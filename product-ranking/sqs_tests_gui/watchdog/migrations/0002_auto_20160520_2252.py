# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('watchdog', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='watchdogjob',
            name='failed_test_run',
        ),
        migrations.AddField(
            model_name='watchdogjob',
            name='failed_test_runs',
            field=models.ManyToManyField(to='watchdog.WatchDogJobTestRuns', null=True, blank=True),
        ),
    ]
