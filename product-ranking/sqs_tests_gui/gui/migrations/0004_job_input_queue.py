# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gui', '0003_auto_20150414_1517'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='input_queue',
            field=models.CharField(default='no', max_length=100, choices=[(b's', b'q'), (b's', b'q'), (b's', b'q')]),
            preserve_default=False,
        ),
    ]
