from django.contrib import admin

# Register your models here.
from models import Users


class UsersAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'active', 'company', 'access_key')
    list_display_links = None

    def has_add_permission(self, request):
        return False

admin.site.register(Users, UsersAdmin)
