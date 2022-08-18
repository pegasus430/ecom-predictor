# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gui', '0008_auto_20150525_1202'),
    ]

    operations = [
        migrations.AlterField(
            model_name='job',
            name='product_urls',
            field=models.CharField(help_text=b'Enter this OR search term above OR product_url. Only for the CH+SC mode!', max_length=1500, null=True, blank=True),
        ),
    ]
