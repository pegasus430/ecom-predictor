# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gui', '0009_auto_20150525_1218'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='job',
            name='product_urls',
        ),
        migrations.AddField(
            model_name='job',
            name='products_urls',
            field=models.CharField(help_text=b'Enter this OR search term above OR product_url. Only for the CH+SC mode!', max_length=1500, null=True, blank=True),
        ),
    ]
