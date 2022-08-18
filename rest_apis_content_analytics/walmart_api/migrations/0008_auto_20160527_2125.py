# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('walmart_api', '0007_auto_20160527_2122'),
    ]

    operations = [
        migrations.AddField(
            model_name='submissionxmlfile',
            name='created',
            field=models.DateTimeField(default=datetime.datetime(2016, 5, 27, 21, 25, 43, 780209, tzinfo=utc), auto_now_add=True),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='submissionxmlfile',
            name='xml_file',
            field=models.FileField(default=None, help_text=b'The actual XML file sent to Walmart', upload_to=b'walmart_xml_files/%Y-%m-%d/'),
            preserve_default=False,
        ),
    ]
