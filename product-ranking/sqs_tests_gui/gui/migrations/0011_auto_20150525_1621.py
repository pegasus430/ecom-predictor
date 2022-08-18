# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gui', '0010_auto_20150525_1220'),
    ]

    operations = [
        migrations.RenameField(
            model_name='job',
            old_name='products_urls',
            new_name='product_urls',
        ),
    ]
