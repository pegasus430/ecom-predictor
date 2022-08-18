# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gui', '0002_auto_20150412_1053'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='branch_name',
            field=models.CharField(help_text=b'Branch to use at the instance(s); leave blank for master', max_length=100, null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='job',
            name='with_best_seller_ranking',
            field=models.BooleanField(default=False, help_text=b'For Walmart bestsellers matching'),
        ),
    ]
