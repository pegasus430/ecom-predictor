from django.contrib import admin

# Register your models here.
from models import SubmissionStatus, SubmissionHistory, SubmissionXMLFile, \
    SubmissionResults, SubmissionResults


admin.site.register(SubmissionStatus)


@admin.register(SubmissionXMLFile)
class SubmissionXMLFileAdmin(admin.ModelAdmin):
    list_display = ['feed_id', 'xml_file', 'created']
    search_fields = ['feed_id']


@admin.register(SubmissionHistory)
class SubmissionHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'feed_id', 'created', 'server_name', 'client_ip']
    search_fields = ['feed_id', 'user__username', 'server_name', 'client_ip']


@admin.register(SubmissionResults)
class SubmissionResultsAdmin(admin.ModelAdmin):
    list_filter = ['feed_id', 'updated']
