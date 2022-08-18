# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('walmart_api', '0006_submissionhistory_xml_file'),
    ]

    operations = [
        migrations.CreateModel(
            name='SubmissionXMLFile',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('feed_id', models.CharField(max_length=50)),
                ('xml_file', models.FileField(help_text=b'The actual XML file sent to Walmart', null=True, upload_to=b'walmart_xml_files/%Y-%m-%d/', blank=True)),
            ],
        ),
        migrations.RemoveField(
            model_name='submissionhistory',
            name='xml_file',
        ),
    ]
