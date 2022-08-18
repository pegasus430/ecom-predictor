# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tests_app', '0002_auto_20151031_2331'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='spider',
            name='active',
        ),
    ]
