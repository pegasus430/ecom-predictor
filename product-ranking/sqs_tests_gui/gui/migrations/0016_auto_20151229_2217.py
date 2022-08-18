# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gui', '0015_jobgroupercache'),
    ]

    operations = [
        migrations.RenameField(
            model_name='job',
            old_name='save_s3_cache',
            new_name='save_raw_pages',
        ),
        migrations.AlterField(
            model_name='job',
            name='branch_name',
            field=models.CharField(help_text=b'Branch to use at the instance(s); leave blank for sc_production', max_length=100, null=True, blank=True),
        ),
    ]
