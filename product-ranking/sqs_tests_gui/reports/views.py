import os
import sys
import json

from django.views.generic import FormView, View
from django.http import HttpResponse
from django.core.urlresolvers import reverse_lazy
from django.contrib.sites.models import Site

from fcgi.views import AuthViewMixin


CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(CWD, '..', '..', 's3_reports'))

from forms import ReportDateForm
from utils import run_report_generation, get_report_fname, dicts_to_ordered_lists, \
    report_to_csv, encrypt, decrypt


SCRIPT_DIR = REPORTS_DIR = os.path.join(CWD, '..', '..', 's3_reports')
LIST_FILE = os.path.join(CWD, '..', 'gui', 'management', 'commands', "_amazon_listing.txt")


class ReportSQSJobs(AuthViewMixin, FormView):
    template_name = 'sqs_jobs.html'
    form_class = ReportDateForm

    def get_context_data(self, **kwargs):
        context = super(ReportSQSJobs, self).get_context_data(**kwargs)
        form = self.get_form_class()(self.request.GET)
        if form.is_bound:
            if form.is_valid():
                date = form.cleaned_data.get('date')
                if not os.path.exists(get_report_fname(date)):
                    context['error_msg'] = ("Report does not exist. Now it's already being generated."
                                            "Please wait a few minutes and try again.")
                    run_report_generation(date)
                    return context
                with open(get_report_fname(date), 'r') as fh:
                    reports = json.loads(fh.read())
                context['by_server'] = sorted([(server, data) for server, data in
                                               dicts_to_ordered_lists(reports['by_server']).items()])
                context['by_spider'] = sorted([(spider, data) for spider, data in
                                               dicts_to_ordered_lists(reports['by_spider']).items()])

                # generate CSV files
                csv_by_server = report_to_csv(["server", "spider", "num of jobs"], context['by_server'])
                csv_by_site = report_to_csv(["spider", "server", "num of jobs"], context['by_spider'])

                site = Site.objects.get_current()

                context['csv_by_server'] = 'http://' + site.domain + str(reverse_lazy(
                    'report-get-csv',
                    kwargs={'encrypted_filename': encrypt(csv_by_server)}
                ))
                context['csv_by_site'] = 'http://' + site.domain + str(reverse_lazy(
                    'report-get-csv',
                    kwargs={'encrypted_filename': encrypt(csv_by_site)}
                ))

        return context


class ReportDownloadCSV(View):
    def get(self, request, *args, **kwargs):
        fname = kwargs.get('encrypted_filename', '')
        if isinstance(fname, unicode):
            fname = fname.encode('utf8')
        try:
            fname = decrypt(fname)
        except:
            fname = decrypt(fname[0:-1])  # remove ending slash?
        if not fname.startswith('/tmp/'):
            return HttpResponse('')
        if not os.path.exists(fname):
            return HttpResponse('')
        response = HttpResponse(open(fname, 'r').read(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="%s.csv"' % fname
        return response
