# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tests_app', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='alert',
            name='when_created',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
    ]
