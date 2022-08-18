from django.contrib import admin

# Register your models here.
from models import Query


class QueryAdmin(admin.ModelAdmin):
    date_hierarchy = 'date'
    list_display = ('user', 'remote_address', 'request_method', 'request_path',
                    'request_body', 'response_status', 'date', 'run_time')

    list_display_links = None

    def has_add_permission(self, request):
        return False



admin.site.register(Query, QueryAdmin)