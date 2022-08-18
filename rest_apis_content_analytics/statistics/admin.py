from django.contrib import admin

# Register your models here.

from .models import SubmitXMLItem, ErrorText, ItemMetadata


class ErrorTextInline(admin.TabularInline):
    model = ErrorText


class ItemMetadataInline(admin.TabularInline):
    model = ItemMetadata


@admin.register(SubmitXMLItem)
class SubmitXMLItemAdmin(admin.ModelAdmin):
    list_display = ['user', 'auth', 'status', 'when', 'multi_item', 'metadata']
    list_filter = ['user', 'auth', 'status', 'when', 'multi_item']
    search_fields = ['user__username', 'item_metadata__upc', 'item_metadata__feed_id']

    inlines = [ItemMetadataInline, ErrorTextInline]

    ordering = ['-when']


@admin.register(ItemMetadata)
class ItemMetadataAdmin(admin.ModelAdmin):
    list_display = ['item', 'upc', 'feed_id']
    search_fields = ['upc', 'feed_id']
