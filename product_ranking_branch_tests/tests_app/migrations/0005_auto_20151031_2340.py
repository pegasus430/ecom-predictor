# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tests_app', '0004_auto_20151031_2339'),
    ]

    operations = [
        migrations.AlterField(
            model_name='testrun',
            name='skip_urls',
            field=models.CharField(help_text=b'All URLs containing this pattern will be skipped', max_length=150, null=True, blank=True),
        ),
    ]
