# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('gui', '0012_job_sc_ch_mode'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='load_s3_cache',
            field=models.DateField(default=datetime.date(2015, 7, 3), help_text=b'Load raw cache from S3', null=True, blank=True),
        ),
        migrations.AddField(
            model_name='job',
            name='save_s3_cache',
            field=models.BooleanField(default=False, help_text=b'Upload raw cache to S3?'),
        ),
    ]
