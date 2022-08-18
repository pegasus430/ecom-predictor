from django.views.generic import TemplateView, View
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.http.response import JsonResponse
from django.core.urlresolvers import reverse_lazy

from models import SubmitXMLItem
from context_processors import _failed_xml_items, _successful_xml_items, \
    _today_all_xml_items, _today_successful_xml_items


class StatsView(TemplateView):
    template_name = 'stats.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(StatsView, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(StatsView, self).get_context_data(**kwargs)
        result = {
            'all_walmart_xml_items': SubmitXMLItem.objects.filter(user=self.request.user).order_by('-when').distinct(),
            'failed_walmart_xml_items': _failed_xml_items(self.request.user),
            'successful_walmart_xml_items': _successful_xml_items(self.request.user),
            'today_all_xml_items': _today_all_xml_items(self.request.user),
            'today_successful_xml_items': _today_successful_xml_items(self.request.user),
        }
        context['breadcrumblist'] = [('Statistics', self.request.path)]
        context.update(result)
        return context

"""
class GetStatsAjax(View):
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated():
            return JsonResponse({})

        return JsonResponse({
            'stats_all_walmart_xml_items': SubmitXMLItem.objects.filter(
                user=request.user).order_by('-when').distinct().count(),
            'stats_failed_walmart_xml_items': SubmitXMLItem.failed_xml_items(request).count(),
            'stats_successful_walmart_xml_items': SubmitXMLItem.successful_xml_items(request).count(),
            'stats_today_all_xml_items': SubmitXMLItem.today_all_xml_items(request).count(),
            'stats_today_successful_xml_items': SubmitXMLItem.today_successful_xml_items(request).count(),
        })
"""