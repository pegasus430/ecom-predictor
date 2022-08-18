# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gui', '0017_job_priority'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='slack_username',
            field=models.CharField(max_length=255, blank=True, null=True, help_text='Enter your @username'),
        ),
    ]
