# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gui', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='with_best_seller_ranking',
            field=models.BooleanField(default=False, help_text=b'For Amazon bestsellers'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='job',
            name='status',
            field=models.CharField(default=b'created', max_length=100, choices=[(b'created', b'created'), (b'pushed into sqs', b'pushed into sqs'), (b'in progress', b'in progress'), (b'finished', b'finished'), (b'failed', b'failed')]),
        ),
    ]
