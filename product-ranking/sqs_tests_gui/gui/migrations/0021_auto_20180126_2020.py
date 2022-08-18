# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gui', '0020_auto_20180125_1147'),
    ]

    operations = [
        migrations.AlterField(
            model_name='job',
            name='name',
            field=models.CharField(help_text=b'Optional, just for convenience', max_length=500, null=True, blank=True),
        ),
    ]
