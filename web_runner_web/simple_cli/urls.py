from django.conf.urls import patterns, url
from simple_cli import views

urlpatterns = patterns('',
    url(r'^$', views.index, name='index'),
    url(r'status/$', views.web_runner_status, name='web_runner_status'),
    url(r'logs/$', views.web_runner_logs, name='web_runner_logs'),
    url(r'logs/(?P<logfile_id>\d+)/$', views.web_runner_logs_view, 
      name='web_runner_logs_view'),
    url(r'lastrequests/$', views.web_runner_lastrequests, 
      name='web_runner_lastrequests'),
    url(r'lastrequests/(?P<n>\d+)/$', views.web_runner_lastrequests, 
      name='web_runner_lastrequests'),
    url(r'lastrequests/history/(?P<requestid>\d+)/$', views.web_runner_request_history, 
      name='web_runner_request_history'),
)
# vim: set expandtab ts=4 sw=2:
