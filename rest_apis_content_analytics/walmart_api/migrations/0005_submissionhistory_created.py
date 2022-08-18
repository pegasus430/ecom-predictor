# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('walmart_api', '0004_auto_20160527_1923'),
    ]

    operations = [
        migrations.AddField(
            model_name='submissionhistory',
            name='created',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
    ]
