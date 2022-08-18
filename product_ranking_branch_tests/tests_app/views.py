import os
import sys

from django.views.generic import DetailView, ListView, TemplateView
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.http import HttpResponse

from .models import Spider, Report, ReportSearchterm
import settings


CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(CWD,  '..', '..', '..',
                             'deploy', 'sqs_ranking_spiders'))


class AdminOnlyMixin(object):
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return HttpResponse('you must be admin')
        return super(AdminOnlyMixin, self).dispatch(request, *args, **kwargs)


class SpidersView(AdminOnlyMixin, ListView):
    template_name = 'spiders.html'
    context_object_name = 'spiders'
    model = Spider

    def get_ordering(self):
        return 'name'


class ReportsView(AdminOnlyMixin, ListView):
    template_name = 'reports.html'
    context_object_name = 'reports'
    model = Report

    def get_queryset(self, *args, **kwargs):
        self.spider_name = self.kwargs['spider']
        self.spider = Spider.objects.get(name=self.spider_name)
        return Report.objects.filter(testrun__spider=self.spider)\
            .order_by('-when_created').distinct()

    def get_context_data(self, **kwargs):
        context = super(ReportsView, self).get_context_data(**kwargs)
        context['spider'] = self.spider
        return context


class DiffsView(AdminOnlyMixin, TemplateView):
    template_name = 'diffs.html'

    def get_context_data(self, **kwargs):
        context = super(DiffsView, self).get_context_data(**kwargs)
        report_searchterm = ReportSearchterm.objects.get(
            pk=self.kwargs['report_searchterm'])
        context['searchterm'] = report_searchterm
        return context