# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gui', '0019_queue_max_length'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='group_id',
            field=models.PositiveIntegerField(db_index=True, null=True, blank=True),
        ),
    ]
