from django.conf.urls import patterns, include, url

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'web_runner_web.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),

#    url(r'^admin/', include(admin.site.urls)),
    url(r'^simple_cli/', include('simple_cli.urls')),
    url(r'^login/$', 'django.contrib.auth.views.login'),
#    url(r'^logout/$', 'django.contrib.auth.views.logout'),
    url(r'^logout/$', 'django.contrib.auth.views.logout', {'template_name': 'registration/logout.html'}),
    
)
