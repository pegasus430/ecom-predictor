from django.conf.urls import include, url
from django.contrib import admin
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

from gui.views import LogFileView, CSVDataFileView, AddJob, ProgressMessagesView,\
    ProgressFileView, SearchFilesView, GetS3FileView, SearchS3Cache, \
    RenderS3CachePage, ViewBase64Image, DataViewer
from sqs_stats.views import SQSAutoscaleStats
from kill_servers.views import KillRestoreServersView
from reports.views import ReportSQSJobs, ReportDownloadCSV

from django.conf import settings
from django.conf.urls.static import static

from immediate.views import immediate_run

urlpatterns = [
    # Examples:
    # url(r'^$', 'gui.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),

    url(r'^admin/', include(admin.site.urls)),

    url(r'^log/(?P<job>[0-9]+)/$', LogFileView.as_view(),
        name='log_file_view'),
    url(r'^data/(?P<job>[0-9]+)/$', CSVDataFileView.as_view(),
        name='csv_data_file_view'),
    url(r'^progress/(?P<job>[0-9]+)/$', ProgressFileView.as_view(),
        name='progress_file_view'),
    url(r'^add-job', csrf_exempt(AddJob.as_view()),
        name='add_job_view'),
    url(r'^view-base64-image/(?P<job>[0-9]+)/$', ViewBase64Image.as_view(),
        name='view_base64_image'),
    url(r'^progress/', ProgressMessagesView.as_view(), name='progress'),
    url(r'^search-files/', SearchFilesView.as_view(), name='search-files'),
    url(r'^get-file/', GetS3FileView.as_view(), name='get-file'),
    url(r'^s3-cache/$', SearchS3Cache.as_view(), name='s3-cache'),
    url(r'^sqs-stats/$', SQSAutoscaleStats.as_view(), name='sqs-stats'),
    url(r'^kill-restore-servers/$', KillRestoreServersView.as_view(), name='kill-restore-servers'),
    url(r'^render-s3-cache/$', RenderS3CachePage.as_view(), name='render-s3-cache'),

    url(r'^reports/sqs-jobs/$', ReportSQSJobs.as_view(), name='report-sqs-jobs'),
    url(r'^reports/get-csv/(?P<encrypted_filename>.+)',
        ReportDownloadCSV.as_view(), name='report-get-csv'),

    url(r'^data/(?P<job>[0-9]+)/viewer/$', DataViewer.as_view(), name='data_file_viewer'),
    url(r'^data/(?P<job>[0-9]+)/viewer/(?P<index>[0-9]+)/$', DataViewer.as_view(), name='data_file_viewer_item'),

    url(r'^immediate/$', login_required(immediate_run), name='immediate'),

    url('^fcgi/$', include('fcgi.urls'))
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)