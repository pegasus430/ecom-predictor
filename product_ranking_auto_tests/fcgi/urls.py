from django.conf.urls import patterns, url
from .views import ReloadFcgiView

urlpatterns = patterns(
    '',
    url('^$', ReloadFcgiView.as_view())
)