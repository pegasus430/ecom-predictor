# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Job',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(help_text=b'Optional, just for convenience', max_length=100, null=True, blank=True)),
                ('spider', models.CharField(max_length=100)),
                ('search_term', models.CharField(help_text=b'Enter this OR product URL below', max_length=255, null=True, blank=True)),
                ('product_url', models.URLField(help_text=b'Enter this OR search term above', max_length=500, null=True, blank=True)),
                ('quantity', models.IntegerField(default=20, help_text=b'Leave blank for unlimited results (slow!)', null=True, blank=True)),
                ('task_id', models.IntegerField(default=100000)),
                ('server_name', models.CharField(default=b'test_server', max_length=100)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('finished', models.DateTimeField(null=True, blank=True)),
                ('status', models.CharField(default=b'created', max_length=100, choices=[(b'created', b'created'), (b'in work', b'in work'), (b'finished', b'finished'), (b'failed', b'failed')])),
            ],
        ),
    ]
