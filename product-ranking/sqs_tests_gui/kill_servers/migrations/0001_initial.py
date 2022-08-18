# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductionBranchUpdate',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('when_updated', models.DateTimeField(default=datetime.datetime.utcnow)),
                ('last_commit_hashsum', models.CharField(max_length=100, null=True, blank=True)),
            ],
            options={
                'ordering': ('-when_updated',),
            },
        ),
        migrations.CreateModel(
            name='ServerKill',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('started', models.DateTimeField(default=datetime.datetime.utcnow)),
                ('finished', models.DateTimeField(null=True, blank=True)),
                ('branch_update', models.ForeignKey(blank=True, to='kill_servers.ProductionBranchUpdate', null=True)),
                ('manual_restart_by', models.ForeignKey(blank=True, to=settings.AUTH_USER_MODEL, null=True)),
            ],
        ),
    ]
