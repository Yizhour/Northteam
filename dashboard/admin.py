from django.contrib import admin

from .models import Feature, FeatureAccess


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ('name', 'key', 'url_name', 'sort_order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'key', 'url_name')
    ordering = ('sort_order', 'id')


@admin.register(FeatureAccess)
class FeatureAccessAdmin(admin.ModelAdmin):
    list_display = ('feature', 'role', 'action', 'allowed')
    list_filter = ('role', 'action', 'allowed', 'feature')
    search_fields = ('feature__name', 'feature__key')
