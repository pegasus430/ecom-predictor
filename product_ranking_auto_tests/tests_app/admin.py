from django.contrib import admin
from django.conf import settings

from .models import ThresholdSettings, Spider, TestRun, FailedRequest, Alert


class ThresholdSettingsAdmin(admin.ModelAdmin):
    list_display = ['n_errors_in_row', 'percent_of_failed_requests', 'notify']
admin.site.register(ThresholdSettings, ThresholdSettingsAdmin)


#class FailedRequestInline(admin.StackedInline):
#    model = FailedRequest
#    max_num = 20


class FailedRequestAdmin(admin.ModelAdmin):
    def partial_error(self):
        return self.error[0:50] + '...' if self.error else ''

    list_display = ['test_run', 'request', partial_error, 'when_created']
    search_fields = ['test_run__spider__name']
    list_filter = ['test_run__spider']
    ordering = ['test_run', '-when_created']
admin.site.register(FailedRequest, FailedRequestAdmin)


#class TestRunInline(admin.StackedInline):
#    model = TestRun
#    max_num = 20


class TestRunAdmin(admin.ModelAdmin):
    list_display = ['spider', 'status', 'when_started', 'when_finished',
                    'num_of_failed_requests', 'num_of_successful_requests']
    search_fields = ['spider__name', 'status']
    list_filter = ['spider', 'status']
    #inlines = [FailedRequestInline]
    ordering = ['spider', '-when_started']
admin.site.register(TestRun, TestRunAdmin)


class SpiderAdmin(admin.ModelAdmin):
    list_display = ['name', 'threshold_settings', 'n_errors_in_row',
                    'percent_of_failed_requests', 'notify', 'active',
                    'is_error']
    search_fields = ['name']
    list_filter = ['active']
    #inlines = [TestRunInline]
    ordering = ['name']
admin.site.register(Spider, SpiderAdmin)


if settings.DEBUG:
    admin.site.register(Alert)