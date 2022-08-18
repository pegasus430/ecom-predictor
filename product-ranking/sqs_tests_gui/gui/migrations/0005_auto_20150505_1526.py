# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gui', '0004_job_input_queue'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='job',
            name='input_queue',
        ),
        migrations.AddField(
            model_name='job',
            name='mode',
            field=models.CharField(default=(b'no cache', b'no cache'), help_text=b'Use test or dev branch!', max_length=100, choices=[(b'no cache', b'no cache'), (b'cache', b'cache')]),
            preserve_default=True,
        ),
    ]
