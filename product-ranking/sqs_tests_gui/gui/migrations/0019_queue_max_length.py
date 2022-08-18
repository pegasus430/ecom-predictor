# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gui', '0018_job_slack'),
    ]

    operations = [
        migrations.AlterField(
            model_name='job',
            name='priority',
            field=models.CharField(max_length=100, default='qa_test'),
        ),
    ]
