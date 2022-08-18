import os
import sys
import random
import re
import time

from django import forms

from .models import Job
from .fields import CustomSelectWidget


CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(CWD, '..', '..', 'monitoring'))
SPIDERS_DIR = os.path.join(CWD, '..', '..', 'product_ranking', 'spiders')
from deploy_to_monitoring_host import find_spiders


def generate_spider_choices():
    result = []
    for spider in find_spiders(SPIDERS_DIR):
        if not spider:
            continue
        if len(spider) < 2:
            continue
        spider_name, spider_domain = spider[0], spider[1]
        if ',' in spider_domain:
            spider_domain = spider_domain.split(',')[0].strip()
        spider_domain = spider_domain.replace('www.', '')
        result.append([spider_name, spider_name + ' [%s]' % spider_domain])
    return sorted(result)


def generate_task_id(from_int, to_int, initial=0):
    return initial + random.randint(from_int, to_int)


class ReadOnlyWidget(forms.widgets.Widget):
    def render(self, _, value, attrs=None):
        return '<b>%s</b>' % value


class JobForm(forms.ModelForm):
    product_urls = forms.CharField(
        required=False,
        initial='',
        help_text="Enter list of urls for new scrapers. One per line",
        widget=forms.Textarea(attrs={'cols': 150})
    )

    product_urls_file = forms.FileField(
        required=False,
        initial='',
        help_text="File with list of urls for new scrapers")

    product_url_job_name = forms.BooleanField(
        required=False,
        initial='',
        label='Use URL for job name',
        help_text='If checked creates jobs with product url as the name'
    )

    def __init__(self, *args, **kwargs):
        super(JobForm, self).__init__(*args, **kwargs)
        self.fields['task_id'].initial = generate_task_id(10000, 99999, self.fields['task_id'].initial)

        request = getattr(self, 'request', None)
        if request:
            slack_username = request.session.get('slack_username')
            if slack_username:
                self.fields['slack_username'].initial = slack_username

        self.fields['spider'] = forms.CharField(
            help_text='Start entering a spider name to see autocompletion',
            widget=CustomSelectWidget(choices=generate_spider_choices()))
        if self.instance and self.instance.pk:
            for field in self.fields.keys():
                self.fields[field].widget = ReadOnlyWidget()
            # TODO: remove save and 'save and continue editing' buttons if the form has instance
        # TODO: remove 'save and continue editing' button

    def save(self, commit=True):
        job = super(JobForm, self).save(commit=False)

        product_url = self.cleaned_data['product_url']
        if product_url:
            if self.cleaned_data['product_url_job_name']:
                job.name = product_url

        product_urls = self.cleaned_data['product_urls']
        if product_urls:
            group_id = int(time.time())
            job.group_id = group_id

            for product_url in product_urls:
                # clone job
                job.pk = None
                job.task_id = generate_task_id(0, 999999, 1000000)
                job.product_url = product_url

                if self.cleaned_data['product_url_job_name']:
                    job.name = product_url

                job.save()

        return job

    def clean(self, *args, **kwargs):
        data = self.cleaned_data
        product_url = data.get('product_url', '')
        search_term = data.get('search_term', '')

        product_urls = data.get('product_urls_file') or data.get('product_urls', '')

        if not product_url and not search_term and not product_urls:
            raise forms.ValidationError(
                'You should enter product url OR list of urls OR search term')

        data['product_urls'] = product_urls

        return data

    def clean_product_url(self, *args, **kwargs):
        data = self.cleaned_data
        product_url = data.get('product_url', '')

        if product_url:
            product_url = product_url.strip()

            if not re.match('https?://', product_url.lower()):
                raise forms.ValidationError('Invalid URL')

        return product_url

    def clean_product_urls(self, *args, **kwargs):
        data = self.cleaned_data
        product_urls = data.get('product_urls', '')

        if product_urls:
            urls = []
            product_urls = re.sub(r'\s+', '\n', product_urls)

            for prod_url in product_urls.splitlines():
                if prod_url:
                    if not re.match('https?://', prod_url.lower()):
                        raise forms.ValidationError('Invalid URL: ' + prod_url)

                    urls.append(prod_url)

            return urls

    def clean_product_urls_file(self, *args, **kwargs):
        data = self.cleaned_data
        product_urls_file = data.get('product_urls_file')

        if product_urls_file:
            urls = []

            for prod_url in product_urls_file:
                prod_url = prod_url.strip()

                if prod_url:
                    if not re.match('https?://', prod_url.lower()):
                        raise forms.ValidationError('Invalid URL: ' + prod_url)

                    urls.append(prod_url)

            return urls

    def clean_slack_username(self, *args, **kwargs):
        data = self.cleaned_data
        slack_username = data.get('slack_username', '')
        if slack_username and not slack_username.startswith('@'):
                slack_username = '@' + slack_username
        request = getattr(self, 'request', None)
        if request:
            request.session['slack_username'] = slack_username
            request.session.set_expiry(60*60*24*365)

        return slack_username

    class Meta:
        model = Job
        exclude = ['created', 'status', 'finished', 'group_id']
