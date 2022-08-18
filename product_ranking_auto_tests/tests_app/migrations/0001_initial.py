# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Alert',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
            ],
        ),
        migrations.CreateModel(
            name='FailedRequest',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('request', models.CharField(max_length=150)),
                ('when_created', models.DateTimeField(auto_now_add=True)),
                ('error', models.TextField(help_text=b'Found errors (if any)', null=True, blank=True)),
                ('error_html', models.TextField(help_text=b'Found errors (in HTML format)', null=True, blank=True)),
                ('result_file', models.FileField(null=True, upload_to=b'', blank=True)),
                ('log_file', models.FileField(null=True, upload_to=b'', blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='Spider',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(help_text=b'Like walmart_products', unique=True, max_length=100)),
                ('n_errors_in_row', models.IntegerField(help_text=b'Num of consecutive errors before sending an alert (override global `threshold settings` if needed)', null=True, blank=True)),
                ('percent_of_failed_requests', models.IntegerField(help_text=b'Percent of total failed requests before sending an alert(override global `threshold settings` if needed)', null=True, blank=True)),
                ('notify', models.CharField(help_text=b'Enter all recipients who will receive alerts (separate emails by comma) - you may override the global`threshold settings` value', max_length=400, null=True, blank=True)),
                ('active', models.BooleanField(default=True, help_text=b'Uncheck to disable checking of this spider')),
            ],
        ),
        migrations.CreateModel(
            name='TestRun',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('when_started', models.DateTimeField(auto_now_add=True)),
                ('when_finished', models.DateTimeField(null=True, blank=True)),
                ('status', models.CharField(default=b'stopped', max_length=20, choices=[(b'stopped', b'stopped'), (b'running', b'running'), (b'passed', b'passed'), (b'failed', b'failed')])),
                ('num_of_failed_requests', models.IntegerField(default=0, help_text=b'Num of failed requests after testing')),
                ('num_of_successful_requests', models.IntegerField(default=0, help_text=b'Num of successfull requests after testing')),
                ('spider', models.ForeignKey(related_name='spider_test_runs', to='tests_app.Spider')),
            ],
        ),
        migrations.CreateModel(
            name='ThresholdSettings',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('n_errors_in_row', models.IntegerField(help_text=b'Num of consecutive errors (failed test runs) before sending an alert')),
                ('percent_of_failed_requests', models.IntegerField(help_text=b'Percent of total failed requests before sending an alert')),
                ('notify', models.CharField(help_text=b'Enter all recipients who will receive alerts (separate emails by comma)', max_length=400)),
            ],
        ),
        migrations.AddField(
            model_name='spider',
            name='threshold_settings',
            field=models.ForeignKey(to='tests_app.ThresholdSettings'),
        ),
        migrations.AddField(
            model_name='failedrequest',
            name='test_run',
            field=models.ForeignKey(related_name='test_run_failed_requests', to='tests_app.TestRun'),
        ),
        migrations.AddField(
            model_name='alert',
            name='test_run',
            field=models.ForeignKey(related_name='test_run_alerts', to='tests_app.TestRun'),
        ),
    ]
