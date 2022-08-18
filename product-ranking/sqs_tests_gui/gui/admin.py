import os
import json
import re

from django.contrib import admin
from django.core.urlresolvers import reverse_lazy

# Register your models here.
from .models import Job, JobGrouperCache, get_progress_filename
from .forms import JobForm

from settings import MEDIA_ROOT


COLORS = {
    'error': 'red',
    'success': 'green'
}


def get_job_id(job):
    if not isinstance(job, int):
        return job.pk

    return job


def link_to_csv_data_file(job):
    return reverse_lazy('csv_data_file_view', kwargs={'job': get_job_id(job)})


def link_to_data_file_viewer(job):
    return reverse_lazy('data_file_viewer', kwargs={'job': get_job_id(job)})


def link_to_data_file_viewer_item(job, index):
    return reverse_lazy('data_file_viewer_item', kwargs={'job': get_job_id(job), 'index': index})


def link_to_data(job):
    link = link_to_csv_data_file(job)
    viewer_link = link_to_data_file_viewer(job)

    viewer_js = "window.open(this.href, 'viewer_{}', 'location=no, status=no, toolbar=no, menubar=no, " \
                "scrollbars=yes, resizable=yes');return false;".format(get_job_id(job))

    if job.priority == 'new_scrapers':
        title = 'JL'
    else:
        title = 'CSV'

    return '<a href="{link}">{title}</a> | <a href="{viewer_link}" onclick="{viewer_js}">Viewer</a>'.format(
        link=link, viewer_link=viewer_link, title=title, viewer_js=viewer_js)

link_to_data.allow_tags = True


def link_to_log_file(job):
    if not isinstance(job, int):
        job = job.pk
    return reverse_lazy('log_file_view', kwargs={'job': job})


def link_to_progress_file(job):
    if not isinstance(job, int):
        job = job.pk
    return reverse_lazy('progress_file_view', kwargs={'job': job})


def admin_link_to_log_file(job):
    return "<a href='%s'>Log</a>" % (link_to_log_file(job))
admin_link_to_log_file.allow_tags = True


def admin_link_to_progress_file(job):
    # try to read progress from the file
    if not os.path.exists(MEDIA_ROOT + get_progress_filename(job)):
        return "<a href='%s'>Progress</a>" % (link_to_progress_file(job))
    else:
        with open(MEDIA_ROOT + get_progress_filename(job)) as fh:
            cont = fh.read()
        try:
            cont = json.loads(cont)
        except Exception as e:
            return "<a href='%s'>(Invalid JSON)</a>" % (link_to_progress_file(job))
        if not isinstance(cont, dict):
            return "<a href='%s'>(Not DICT)</a>" % (link_to_progress_file(job))
        progress = cont.get('progress', -1)
        return "<a href='%s'>%s products</a>" % (link_to_progress_file(job), progress)
admin_link_to_progress_file.allow_tags = True


def admin_status(job):
    _template = "<span style='color:%s; font-weight:%s'>%s</span>"
    if job.status.lower() == 'finished':
        return _template % ('green', '', job.status)
    elif job.status.lower() == 'failed':
        return _template % ('red', '', job.status)
    elif job.status.lower() == 'pushed into sqs':
        return _template % ('', 'bold', job.status)
    elif job.status.lower() == 'in progress':
        return _template % ('blue', 'bold', job.status)
    return job.status
admin_status.allow_tags = True


def admin_name_with_url(job):
    name = job.name

    if name:
        urls = re.compile(r"((https?):((//)|(\\\\))+[\w\d:#@%/;$()~_?\+-=\\\.&]*)", re.MULTILINE | re.UNICODE)
        name = urls.sub(r'<a href="\1" target="_blank">\1</a>', name)

    return name
admin_name_with_url.allow_tags = True


class JobAdmin(admin.ModelAdmin):
    list_display = (
        'task_id', 'spider', admin_name_with_url, 'branch_name', admin_status,
        'created', 'finished',
        link_to_data, Job.view_as_image, 'priority', 'searchterm_or_url'
        # , admin_link_to_log_file

    )
    list_filter = ('status', 'created', 'finished', 'priority')
    search_fields = ('name', 'spider', 'product_url', 'branch_name',
                     'search_term', 'task_id')
    form = JobForm

    def reset_status_to_created(self, request, qs, *args, **kwargs):
        qs.update(status='created')

    def reset_status_to_pushed_into_sqs(self, request, qs, *args, **kwargs):
        qs.update(status='pushed into sqs')

    def get_form(self, request, *args, **kwargs):
        form = super(JobAdmin, self).get_form(request, *args, **kwargs)
        form.request = request
        return form

    actions = (reset_status_to_created, reset_status_to_pushed_into_sqs)


admin.site.register(Job, JobAdmin)

admin.site.register(JobGrouperCache)