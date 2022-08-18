# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('walmart_api', '0008_auto_20160527_2125'),
    ]

    operations = [
        migrations.AlterField(
            model_name='submissionxmlfile',
            name='created',
            field=models.DateTimeField(default=datetime.datetime.utcnow),
        ),
        migrations.AlterField(
            model_name='submissionxmlfile',
            name='xml_file',
            field=models.FileField(help_text=b'The actual XML file sent to Walmart', upload_to=b''),
        ),
    ]
