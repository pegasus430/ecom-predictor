from django.conf.urls import patterns, include, url
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = patterns('',
    url(r'^admin/', include(admin.site.urls)),
    url(r'^tests/', include('tests_app.urls')),

    url(r'^login/$', 'django.contrib.auth.views.login',
        {'template_name': 'login.html'}, name='login_view'),
    url('^fcgi/$', include('fcgi.urls'))
)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)

if 'django_ses' in settings.INSTALLED_APPS:
    urlpatterns += (url(r'^admin/django-ses/', include('django_ses.urls')),)