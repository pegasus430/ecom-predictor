from django.views.generic import TemplateView
from django.http import HttpResponse

from fcgi.views import AuthViewMixin
from models import ServerKill, ProductionBranchUpdate


class KillRestoreServersView(AuthViewMixin, TemplateView):
    template_name = 'kill_servers.html'

    def get_context_data(self, **kwargs):
        context = super(KillRestoreServersView, self).get_context_data(**kwargs)
        # group server kills by branch update
        context['branch_updates'] = ProductionBranchUpdate.objects.all().order_by(
            '-when_updated').distinct()[0:50]
        context['manual_kills'] = ServerKill.objects.filter(
            manual_restart_by__isnull=False).order_by('-started').distinct()[0:50]
        return context

    def post(self, request, *args, **kwargs):
        if ServerKill.objects.filter(started__isnull=False, finished__isnull=True):
            return HttpResponse('There are already some unfinished ServerKills running!')
        if request.POST.get('button_kill', None):
            return HttpResponse('KILL - this is not implemented yet, nothing happened ;)')
        if request.POST.get('button_restore', None):
            return HttpResponse('RESTORE - this is not implemented yet, nothing happened ;)')
        return HttpResponse('Unrecognized action!')
