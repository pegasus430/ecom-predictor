# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gui', '0007_auto_20150525_1142'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='extra_cmd_args',
            field=models.TextField(help_text=b'Extra command-line arguments, 1 per line. Example: enable_cache=1', max_length=300, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='job',
            name='product_urls',
            field=models.URLField(help_text=b'Enter this OR search term above OR product_url. Only for the CH+SC mode!', max_length=1500, null=True, blank=True),
        ),
    ]
