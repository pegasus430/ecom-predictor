# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gui', '0014_remove_job_load_s3_cache'),
    ]

    operations = [
        migrations.CreateModel(
            name='JobGrouperCache',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('spider', models.CharField(max_length=100, db_index=True)),
                ('product_url', models.URLField(max_length=500)),
                ('extra_args', models.TextField(null=True, blank=True)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True, null=True)),
            ],
        ),
    ]
