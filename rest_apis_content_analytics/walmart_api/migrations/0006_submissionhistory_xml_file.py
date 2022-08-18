# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('walmart_api', '0005_submissionhistory_created'),
    ]

    operations = [
        migrations.AddField(
            model_name='submissionhistory',
            name='xml_file',
            field=models.FileField(help_text=b'The actual XML file sent to Walmart', null=True, upload_to=b'walmart_xml_files/%Y-%m-%d/', blank=True),
        ),
    ]
