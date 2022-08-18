# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0005_auto_20160825_1948'),
    ]

    operations = [
        migrations.AlterField(
            model_name='submitxmlitem',
            name='status',
            field=models.CharField(max_length=20, choices=[(b'successful', b'successful'), (b'failed', b'failed')]),
        ),
        migrations.AlterField(
            model_name='submitxmlitem',
            name='when',
            field=models.DateTimeField(default=datetime.datetime.now),
        ),
    ]
