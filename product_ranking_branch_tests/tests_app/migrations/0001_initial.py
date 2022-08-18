# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Report',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('total_urls', models.IntegerField(help_text=b'Do not fill', null=True, blank=True)),
                ('matched_urls', models.IntegerField(help_text=b'Do not fill', null=True, blank=True)),
                ('diffs', jsonfield.fields.JSONField(help_text=b'Do not fill', null=True, blank=True)),
                ('when_created', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='SearchTerm',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('quantity', models.IntegerField(default=300)),
                ('searchterm', models.CharField(max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name='Spider',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(help_text=b'Like walmart_products', unique=True, max_length=100)),
                ('active', models.BooleanField(default=True, help_text=b'Uncheck to disable checking of this spider')),
                ('searchterms', models.ManyToManyField(help_text=b'Choose at least 3', to='tests_app.SearchTerm')),
            ],
        ),
        migrations.CreateModel(
            name='TestRun',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('when_started', models.DateTimeField(auto_now_add=True)),
                ('when_finished', models.DateTimeField(null=True, blank=True)),
                ('branch1', models.CharField(max_length=150)),
                ('branch2', models.CharField(max_length=150)),
                ('status', models.CharField(default=b'stopped', max_length=20, choices=[(b'stopped', b'stopped'), (b'running', b'running'), (b'passed', b'passed'), (b'failed', b'failed')])),
                ('exclude_fields', models.CharField(max_length=500, choices=[(b'fields', b'fields'), (b'__module__', b'__module__'), (b'__doc__', b'__doc__')])),
                ('skip_urls', models.CharField(help_text=b'All URLs containing this pattern will be skipped', max_length=150)),
                ('strip_get_args', models.BooleanField(default=False)),
                ('spider', models.ForeignKey(related_name='spider_test_runs', to='tests_app.Spider')),
            ],
        ),
        migrations.AddField(
            model_name='report',
            name='testrun',
            field=models.ForeignKey(related_name='testrun_reports', to='tests_app.TestRun'),
        ),
    ]
