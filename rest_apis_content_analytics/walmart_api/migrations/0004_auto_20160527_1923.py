# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('walmart_api', '0003_auto_20160311_2148'),
    ]

    operations = [
        migrations.AddField(
            model_name='submissionhistory',
            name='client_ip',
            field=models.IPAddressField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='submissionhistory',
            name='server_name',
            field=models.CharField(max_length=100, null=True, blank=True),
        ),
    ]
