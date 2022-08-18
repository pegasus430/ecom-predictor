# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gui', '0013_auto_20150703_2123'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='job',
            name='load_s3_cache',
        ),
    ]
