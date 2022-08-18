# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('walmart_api', '0009_auto_20160527_2339'),
    ]

    operations = [
        migrations.CreateModel(
            name='SubmissionResults',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('feed_id', models.CharField(max_length=50)),
                ('response', models.TextField()),
                ('updated', models.DateTimeField(default=datetime.datetime.utcnow)),
            ],
        ),
        migrations.AlterField(
            model_name='submissionhistory',
            name='client_ip',
            field=models.CharField(max_length=50, null=True, blank=True),
        ),
    ]
