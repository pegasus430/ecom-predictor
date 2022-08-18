# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('tests_app', '0006_auto_20151101_2254'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReportSearchterm',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('total_urls', models.IntegerField(help_text=b'Do not fill', null=True, blank=True)),
                ('matched_urls', models.IntegerField(help_text=b'Do not fill', null=True, blank=True)),
                ('diffs', jsonfield.fields.JSONField(help_text=b'Do not fill', null=True, blank=True)),
                ('when_created', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='report',
            unique_together=set([]),
        ),
        migrations.AddField(
            model_name='reportsearchterm',
            name='report',
            field=models.ForeignKey(related_name='report_searchterms', to='tests_app.Report'),
        ),
        migrations.AddField(
            model_name='reportsearchterm',
            name='searchterm',
            field=models.ForeignKey(related_name='searchterm_reports', to='tests_app.SearchTerm'),
        ),
        migrations.RemoveField(
            model_name='report',
            name='diffs',
        ),
        migrations.RemoveField(
            model_name='report',
            name='matched_urls',
        ),
        migrations.RemoveField(
            model_name='report',
            name='searchterm',
        ),
        migrations.RemoveField(
            model_name='report',
            name='total_urls',
        ),
    ]
