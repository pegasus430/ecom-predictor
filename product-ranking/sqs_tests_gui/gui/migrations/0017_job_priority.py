# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gui', '0016_auto_20151229_2217'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='priority',
            field=models.CharField(default=b'test', max_length=20, choices=[(b'test', b'test'), (b'urgent', b'urgent'), (b'production', b'production'), (b'dev', b'dev')]),
        ),
    ]
