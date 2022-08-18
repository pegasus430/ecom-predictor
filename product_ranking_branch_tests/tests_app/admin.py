from django.contrib import admin

from .models import SearchTerm, Spider, TestRun, Report, ReportSearchterm,\
    LocalCache
from .forms import TestRunForm


admin.site.register(SearchTerm)
admin.site.register(Spider)
admin.site.register(Report)
admin.site.register(ReportSearchterm)
admin.site.register(LocalCache)


class TestRunAdmin(admin.ModelAdmin):
    form = TestRunForm
admin.site.register(TestRun, TestRunAdmin)