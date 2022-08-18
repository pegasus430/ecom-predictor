# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0004_auto_20160311_2148'),
    ]

    operations = [
        migrations.AlterField(
            model_name='itemmetadata',
            name='feed_id',
            field=models.CharField(db_index=True, max_length=50, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='itemmetadata',
            name='upc',
            field=models.CharField(db_index=True, max_length=20, null=True, blank=True),
        ),
    ]
