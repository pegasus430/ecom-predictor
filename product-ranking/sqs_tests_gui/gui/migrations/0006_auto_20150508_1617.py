# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gui', '0005_auto_20150505_1526'),
    ]

    operations = [
        migrations.AlterField(
            model_name='job',
            name='mode',
            field=models.CharField(default=(b'no cache', b'no cache'), max_length=100, choices=[(b'no cache', b'no cache'), (b'cache', b'cache')]),
        ),
    ]
