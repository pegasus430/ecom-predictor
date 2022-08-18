from django.views.generic import TemplateView

from fcgi.views import AuthViewMixin
from . import get_number_of_messages_in_queues, get_number_of_instances_in_autoscale_groups


class SQSAutoscaleStats(AuthViewMixin, TemplateView):
    template_name = 'sqs_autoscale_stats.html'

    def get_context_data(self, **kwargs):
        # Same config file is used to determine which groups we scale
        # during deploy and which to show on stats ui
        # this will add clusters we want to see on UI, but don't want to scale to 0 during deploy
        clusters_to_add = [u"ScraperCluster_sqs_ranking_spiders_tasks_realtime"]
        context = super(SQSAutoscaleStats, self).get_context_data(**kwargs)
        context['queues_data'] = get_number_of_messages_in_queues()
        context['groups_data'] = get_number_of_instances_in_autoscale_groups(add_groups=clusters_to_add)
        return context
