from django.views.generic import FormView
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse_lazy, NoReverseMatch
from .forms import ReloadFcgiForm


class AuthViewMixin(object):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            try:  # if the view exists
                return HttpResponseRedirect(
                    reverse_lazy('login_view')
                )
            except NoReverseMatch:  # if the view doesn't exist
                return HttpResponse('you must be admin')
        return super(AuthViewMixin, self).dispatch(request, *args, **kwargs)


class ReloadFcgiView(AuthViewMixin, FormView):
    form_class = ReloadFcgiForm
    template_name = 'reload_fcgi.html'
    success_url = '/'

    def form_valid(self, form):
        form.reload_fcgi()
        return super(ReloadFcgiView, self).form_valid(form)