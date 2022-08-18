# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gui', '0011_auto_20150525_1621'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='sc_ch_mode',
            field=models.BooleanField(default=False, help_text=b'Run the spider in CH mode. Do not forget to fill the Product UrlS field above.'),
        ),
    ]
