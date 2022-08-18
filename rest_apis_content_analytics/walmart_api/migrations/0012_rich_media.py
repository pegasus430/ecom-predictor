# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

class Migration(migrations.Migration):

    dependencies = [
        ('walmart_api', '0011_auto_20160914_2200'),
    ]

    operations = [
        migrations.CreateModel(
            name='RichMediaMarketingContent',
            fields=[
                ('marketing_content', models.TextField())
            ],
        ),
    ]
