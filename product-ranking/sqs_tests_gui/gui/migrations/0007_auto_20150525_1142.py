# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gui', '0006_auto_20150508_1617'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='product_urls',
            field=models.URLField(help_text=b'Enter this OR search term above OR product_url', max_length=1500, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='job',
            name='product_url',
            field=models.URLField(help_text=b'Enter this OR search term above OR products URL below', max_length=500, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='job',
            name='search_term',
            field=models.CharField(help_text=b'Enter this OR product(s) URL below', max_length=255, null=True, blank=True),
        ),
    ]
