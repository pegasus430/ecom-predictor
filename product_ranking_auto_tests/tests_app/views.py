import os
import sys

from django.views.generic import DetailView, TemplateView, RedirectView, View
from django.http.response import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.core.urlresolvers import reverse_lazy

from .models import TestRun, Spider, FailedRequest

import settings


CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(1, os.path.join(CWD, '..', '..', 'deploy',
                                'sqs_ranking_spiders'))
from libs import convert_json_to_csv


class AuthViewMixin(object):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return HttpResponseRedirect(
                reverse_lazy('login_view')
            )
        return super(AuthViewMixin, self).dispatch(request, *args, **kwargs)


class DashboardView(AuthViewMixin, TemplateView):
    template_name = 'spiders.html'

    def get_context_data(self, **kwargs):
        context = super(DashboardView, self).get_context_data(**kwargs)
        context['spiders'] = Spider.objects.all().order_by('name')
        return context
    # TODO: failed\success spiders, num of spiders checked in the last 3 days, num of test runs performed in the last 3 days, num of alerts sent (?)


class SpiderReview(AuthViewMixin, DetailView):
    model = Spider
    template_name = 'spider.html'

    def get_context_data(self, **kwargs):
        context = super(SpiderReview, self).get_context_data(**kwargs)
        context['all_runs'] = self.object.spider_test_runs.all()\
            .order_by('-when_finished')
        context['running_runs'] = self.object.get_last_running_test_runs()
        context['failed_runs'] = self.object.get_last_failed_test_runs()
        context['passed_runs'] = self.object.get_last_successful_test_runs()
        return context


class ViewMissingDataRequests24Hours(AuthViewMixin, DetailView):
    model = Spider
    template_name = 'spider_missing.html'

    def get_context_data(self, **kwargs):
        context = super(
            ViewMissingDataRequests24Hours, self).get_context_data(**kwargs)
        context['all_runs'] = self.object.spider_test_runs.all()\
            .order_by('-when_finished')
        context['running_runs'] = self.object.get_last_running_test_runs()
        context['failed_runs'] \
            = self.object.get_failed_test_runs_for_24_hours_with_missing_data()
        context['passed_runs'] = self.object.get_last_successful_test_runs()
        return context


class JSONToCSV(AuthViewMixin, View):
    def get(self, *args, **kwargs):
        _json = kwargs.get('json', None)
        if not _json:
            return HttpResponse('no JSON list passed')
        if not _json.lower().endswith('.jl'):
            return HttpResponse('passed file is not JSON list file')
        if not os.path.exists(_json):  # media url?
            _json = os.path.join(settings.MEDIA_ROOT,
                                 _json.replace(settings.MEDIA_URL[1:], ''))
        if not os.path.exists(_json):
            return HttpResponse('given file does not exist')
        csv_fname = convert_json_to_csv(_json.replace('.jl', ''))
        response = HttpResponse(content=open(csv_fname).read())
        response['Content-Type']= 'text/csv'
        response['Content-Disposition'] = 'attachment; filename=%s' \
                                           % os.path.basename(csv_fname)
        return response


class TestRunReview(AuthViewMixin, DetailView):
    model = TestRun


class SpiderBySpiderName(AuthViewMixin, RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        spider = get_object_or_404(Spider, name=kwargs['name'])
        return reverse_lazy('tests_app_spider_review',
                            kwargs={'pk': spider.pk})