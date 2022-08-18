from django.contrib import admin

from models import WatchDogJob, WatchDogJobTestRuns


class WatchDogJobAdmin(admin.ModelAdmin):
    list_display = ['name', 'created', 'last_checked', 'run_for_days', 'spider',
                    'branch', 'status']
    list_filter = ['status']
admin.site.register(WatchDogJob, WatchDogJobAdmin)


class WatchDogJobTestRunsAdmin(admin.ModelAdmin):
    list_display = ['wd_job', 'created', 'finished', 'spider_job', 'screenshot_job', 'status']
    list_filter = ['status']
admin.site.register(WatchDogJobTestRuns, WatchDogJobTestRunsAdmin)