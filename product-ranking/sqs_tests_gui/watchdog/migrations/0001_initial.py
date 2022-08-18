# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gui', '0016_auto_20151229_2217'),
    ]

    operations = [
        migrations.CreateModel(
            name='WatchDogJob',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(help_text=b'Any name, for convenience', max_length=100, null=True, blank=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('last_checked', models.DateTimeField(null=True, blank=True)),
                ('run_for_days', models.IntegerField(default=5, help_text=b'Num of days the job should be active for')),
                ('spider', models.CharField(help_text=b'Like walmart_products or amazon_products', max_length=100)),
                ('urls', models.TextField(help_text=b'List of URLs to look the desired values in, 1 per line')),
                ('desired_value', models.CharField(help_text=b'Any value will be converted using str()', max_length=150)),
                ('response_path', models.CharField(help_text=b'JsonPath in the output file, see https://github.com/masukomi/jsonpath-perl/tree/master for syntax help', max_length=200)),
                ('branch', models.CharField(help_text=b'Leave blank for sc_production', max_length=100, null=True, blank=True)),
                ('status', models.CharField(default=b'ok', max_length=50, choices=[(b'ok', b'ok'), (b'failed', b'failed')])),
            ],
        ),
        migrations.CreateModel(
            name='WatchDogJobTestRuns',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('finished', models.DateTimeField(null=True, blank=True)),
                ('status', models.CharField(default=b'created', max_length=100, choices=[(b'created', b'created'), (b'pushed into sqs', b'pushed into sqs'), (b'in progress', b'in progress'), (b'finished', b'finished'), (b'failed', b'failed')])),
                ('screenshot_job', models.ForeignKey(to='gui.Job')),
                ('spider_job', models.ForeignKey(related_name='wd_test_run_jobs', to='gui.Job')),
                ('wd_job', models.ForeignKey(to='watchdog.WatchDogJob')),
            ],
        ),
        migrations.AddField(
            model_name='watchdogjob',
            name='failed_test_run',
            field=models.ForeignKey(blank=True, to='watchdog.WatchDogJobTestRuns', null=True),
        ),
    ]
