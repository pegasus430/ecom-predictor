import os
import sys
import datetime
import gzip
import random
import json
import base64
import tempfile
import mimetypes
import StringIO
import zlib
import urlparse
import cPickle as pickle
import cgi

from django.core.servers.basehttp import FileWrapper
from django.views.generic import RedirectView, View, TemplateView
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.http import HttpResponse
import boto
from boto.s3.connection import S3Connection
import csv

from .models import get_data_filename, get_log_filename, get_progress_filename,\
    Job, JobGrouperCache
from .admin import link_to_data_file_viewer, link_to_data_file_viewer_item

from management.commands.update_jobs import LOCAL_AMAZON_LIST,\
    AMAZON_BUCKET_NAME, download_s3_file
from management.commands.download_list_of_s3_cache_files import LOCAL_AMAZON_LIST_CACHE
import settings


CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(CWD,  '..', '..', '..',
                             'deploy', 'sqs_ranking_spiders'))
sys.path.append(os.path.join(CWD,  '..', '..'))
from scrapy_daemon import PROGRESS_QUEUE_NAME
from product_ranking.cache_models import list_db_cache


class AdminOnlyMixin(object):
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return HttpResponse('you must be admin')
        return super(AdminOnlyMixin, self).dispatch(request, *args, **kwargs)


class StaffOnlyMixin(object):
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return HttpResponse('you must be staff')
        return super(StaffOnlyMixin, self).dispatch(request, *args, **kwargs)


class CSVDataFileView(StaffOnlyMixin, RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        data_fname = get_data_filename(kwargs['job'])
        if data_fname.startswith('/'):
            data_fname = data_fname[1:]
        return settings.MEDIA_URL + data_fname


class LogFileView(StaffOnlyMixin, RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        log_fname = get_log_filename(kwargs['job'])
        if log_fname.startswith('/'):
            log_fname = log_fname[1:]
        return settings.MEDIA_URL + log_fname


class ProgressFileView(StaffOnlyMixin, RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        prog_fname = get_progress_filename(kwargs['job'])
        if prog_fname.startswith('/'):
            prog_fname = prog_fname[1:]
        return settings.MEDIA_URL + prog_fname


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


class AddJob(View):
    """ For POSTing jobs """
    def post(self, request, *args, **kwargs):
        if not os.path.exists('/tmp/_enable_add_job'):
            return HttpResponse('/tmp/_enable_add_job does not exist, exit...')

        client_ip = get_client_ip(request)

        site = request.POST.get('site', '')
        searchterms_str = request.POST.get('searchterms_str', '')
        product_url = request.POST.get('product_url', '')

        name = ('AUTO|'+str(client_ip) + '|' + site
                + '|' + searchterms_str)

        if not '_products' in site:
            site = site.strip() + '_products'

        quantity = int(request.POST.get('quantity', 200))

        branch = ''

        if product_url and not searchterms_str:
            # create a new 'grouper' object, not the real job
            JobGrouperCache.objects.get_or_create(
                spider=site, product_url=product_url,
                extra_args=json.dumps({
                    'name': name, 'branch_name': branch
                })
            )
            return HttpResponse('JobGrouperCache object created')
        else:
            Job.objects.get_or_create(
                name=name,
                spider=site,
                search_term=searchterms_str,
                product_url=product_url,
                quantity=quantity,
                task_id=random.randrange(100000, 900000),
                mode='no cache',
                save_raw_pages=True,
                branch_name=branch
            )
            return HttpResponse('Job object created')


class ViewBase64Image(StaffOnlyMixin, View):
    # Displays output file as image

    def get(self, request, *args, **kwargs):
        job = Job.objects.get(pk=kwargs['job'])
        output_fname = get_data_filename(job)
        output_fname = settings.MEDIA_ROOT + output_fname

        if not os.path.exists(output_fname):
            return HttpResponse('Output filename %s for job with ID %s does not exist' %
                                (output_fname, job.pk))
        if ".csv" in output_fname:
            with open(output_fname, 'r') as fh:
                try:
                    csv.field_size_limit(sys.maxsize)
                    reader = csv.DictReader(fh)
                    content = list(reader)[0]['image']
                except:
                    return "Corrupted file"

            return HttpResponse('<img src="data:image/png;base64,%s" />' % content)
        elif ".jl" in output_fname:
            with open(output_fname, 'r') as fh:
                try:
                    parsed_json = json.load(fh)
                    content = parsed_json.get("screenshot")
                except:
                    return "Corrupted file"
            return HttpResponse('<img src="data:image/png;base64,%s" />' % content)

class ProgressMessagesView(StaffOnlyMixin, TemplateView):
    template_name = 'progress_messages.html'
    max_messages = 999

    def _connect(self, name=PROGRESS_QUEUE_NAME, region="us-east-1"):
        self.conn = boto.sqs.connect_to_region(region)
        self.q = self.conn.get_queue(name)

    def _msgs(self, num_messages=100, timeout=3):
        return [base64.b64decode(m.get_body())
                for m in self.q.get_messages(visibility_timeout=timeout)]

    def get_context_data(self, **kwargs):
        context = super(ProgressMessagesView, self).get_context_data(**kwargs)
        self._connect()
        context['msgs'] = self._msgs()
        return context


class SearchFilesView(AdminOnlyMixin, TemplateView):
    template_name = 'search_s3_files.html'
    max_files = 10000
    fname2open = LOCAL_AMAZON_LIST
    extra_filter = None

    def get_context_data(self, **kwargs):
        result = []
        context = super(SearchFilesView, self).get_context_data(**kwargs)
        error = None
        warning = None
        searchterm = self.request.GET.get('searchterm', '')
        if not searchterm:
            return context  # not searched
        elif len(searchterm) < 4:
            error = 'Searchterm must be longer than 4 chars'
        else:
            with open(self.fname2open, 'r') as fh:
                for line in fh:
                    line = line.strip()
                    if '<Key:' in line and ',' in line:
                        line = line.split(',', 1)[1]
                        if line[-1] == '>':
                            line = line[0:-1]
                        if searchterm.lower() in line.lower():
                            if self.extra_filter:
                                # filter by additional filtering str, if needed
                                if self.extra_filter.lower() in line.lower():
                                    result.append(line)
                            else:
                                result.append(line)
                        if len(result) > self.max_files:
                            warning = 'More than %i results matched' % self.max_files
                            break
        context['error'] = error
        context['warning'] = warning
        context['results'] = result
        context['searchterm'] = searchterm
        return context


class GetS3FileView(AdminOnlyMixin, View):
    template_name = 'search_s3_files.html'
    max_files = 400

    def get(self, request, **kwargs):
        fname = request.GET['file']
        ext = os.path.splitext(fname)
        if ext and len(ext) > 1 and isinstance(ext, (list, tuple)):
            ext = ext[1]
        # save to a temporary file
        tempfile_name = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        tempfile_name.close()
        download_s3_file(AMAZON_BUCKET_NAME, fname, tempfile_name.name)
        # create File response
        wrapper = FileWrapper(open(tempfile_name.name, 'rb'))
        content_type = mimetypes.guess_type(tempfile_name.name)[0]
        response = HttpResponse(wrapper, content_type=content_type)
        response['Content-Length'] = os.path.getsize(tempfile_name.name)
        response['Content-Disposition'] = 'attachment; filename=%s' % tempfile_name.name
        return response


#******** S3-cache Views ********
class SearchS3Cache(SearchFilesView):
    # User searches for a URL, the search results are displayed then.
    # User then can choose what cached response to view.
    template_name = 'search_s3_cache.html'
    fname2open = LOCAL_AMAZON_LIST_CACHE
    extra_filter = '__MARKER_URL__'

    def get_context_data(self, *args, **kwargs):
        context = super(SearchS3Cache, self).get_context_data(*args, **kwargs)
        searchterm = self.request.GET.get('searchterm', '')
        if not searchterm:
            context['cache_list'] = list_db_cache()
        return context


class RenderS3CachePage(AdminOnlyMixin, TemplateView):
    # Downloads and renders the selected cache page
    template_name = 'render_cache_page.html'

    @staticmethod
    def _ungzip(what):
        what2 = None
        try:
            what2 = StringIO.StringIO(zlib.decompress(what)).read()
        except:
            try:
                what2 = gzip.GzipFile('', 'rb', 9, StringIO.StringIO(what)).read()
            except:
                pass
        return what2 if what2 is not None else what

    @staticmethod
    def _relative_to_absolute(domain, cont):
        # ugly things like src="//img1.domain.com"
        cont = cont.replace('src="//', 'str="http://')
        cont = cont.replace('src=\'//', 'str=\'http://')
        cont = cont.replace('href="//', 'href="http://')
        cont = cont.replace('href=\'//', 'href=\'http://')
        # normal relative links like src="/images/img.png"
        cont = cont.replace('src="/', 'str="http://%s/' % domain)
        cont = cont.replace('src=\'/', 'str=\'http://%s/' % domain)
        cont = cont.replace('href="/', 'href="http://%s/' % domain)
        cont = cont.replace('href=\'/', 'href=\'http://%s/' % domain)
        return cont

    def get_context_data(self, *args, **kwargs):
        # TODO: proxy to rewrite requests to the original website?
        # (if the resource's link is created dynamically)
        context = super(RenderS3CachePage, self).get_context_data(
            *args, **kwargs)

        fname = self.request.GET['file']
        fname = base64.b32decode(fname)

        # we actually want the response file, not the __MARKER_URL__ file
        fpath = fname.split('__MARKER_URL__', 1)[0]

        ext = os.path.splitext(fname)
        if ext and len(ext) > 1 and isinstance(ext, (list, tuple)):
            ext = ext[1]

        # download S3 files
        bucket_name = 'spiders-cache'

        aws_connection = S3Connection()
        bucket = aws_connection.get_bucket(bucket_name)

        # get response body
        key = bucket.get_key(fpath+'response_body')
        f_content = key.get_contents_as_string()
        f_content = self._ungzip(f_content)

        # get metadata
        key = bucket.get_key(fpath+'pickled_meta')
        metadata = key.get_contents_as_string()
        if metadata:
            metadata = pickle.loads(metadata)
            if 'timestamp' in metadata:
                metadata['datetime'] = datetime.datetime.fromtimestamp(
                    metadata['timestamp'])

        # rewrite relative links to absolute
        original_domain = urlparse.urlparse(metadata['url']).netloc
        f_content = self._relative_to_absolute(original_domain, f_content)

        context['original_content'] = f_content
        context['cache_meta'] = metadata
        return context

    def render_to_response(self, context, **response_kwargs):
        response = super(RenderS3CachePage, self).render_to_response(
            context, **response_kwargs)
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"  # HTTP 1.1.
        response["Pragma"] = "no-cache"  # HTTP 1.0.
        response["Expires"] = "0"  # Proxies.
        return response


class DataViewer(StaffOnlyMixin, TemplateView):

    template_name = 'data_viewer.html'

    def get_context_data(self, **kwargs):
        context = super(DataViewer, self).get_context_data(**kwargs)

        try:
            job = Job.objects.get(pk=context['job'])
        except Job.DoesNotExist:
            context['message'] = 'Job with ID {} does not exist'.format(context['job'])
            return context

        data_filename = get_data_filename(job)
        data_filepath = settings.MEDIA_ROOT + data_filename

        if not os.path.exists(data_filepath):
            context['message'] = 'Data file {} for job with ID {} does not exist'.format(data_filename, job.pk)
            return context

        data = []
        data_type = os.path.splitext(data_filename)[1]

        with open(data_filepath) as data_file:
            if data_type == '.csv':
                data_reader = csv.DictReader(data_file)

                for row in data_reader:
                    data.append(row)
            elif data_type == '.jl':
                for line in data_file:
                    try:
                        data.append(json.loads(line))
                    except:
                        context['message'] = 'File {} corrupted'.format(data_filename)
                        return context

        if not data:
            context['message'] = 'File {} has not data'.format(data_filename)
            return context

        index = context.get('index', 1)
        if index:
            try:
                index = int(index)
            except:
                context['message'] = 'Invalid result index {}'.format(index)
                return context

        if index > len(data):
            index = len(data)
        elif index < 1:
            index = 1

        product = data[index-1]

        context['title'] = product.get('title')
        context['url'] = product.get('url')
        context['data'] = cgi.escape(json.dumps(product, indent=2))

        if len(data) > 1:
            # search term or shelf data
            context['prev_item'] = link_to_data_file_viewer_item(job, index - 1) if index > 1 else None
            context['next_item'] = link_to_data_file_viewer_item(job, index + 1) if index < len(data) else None
            context['total'] = len(data)
            context['index'] = index
        else:
            # product url data
            if job.group_id:
                group_jobs = Job.objects.filter(group_id=job.group_id).order_by('pk')

                total = 0
                buf_job = None

                for group_index, group_job in enumerate(group_jobs, 1):
                    if group_job.pk == job.pk:
                        context['index'] = group_index
                        context['prev_item'] = link_to_data_file_viewer(buf_job) if buf_job else None
                    elif 'prev_item' in context and 'next_item' not in context:
                        context['next_item'] = link_to_data_file_viewer(group_job)

                    buf_job = group_job
                    total += 1

                context['total'] = total
            else:
                context['total'] = 1
                context['index'] = 1

        return context

