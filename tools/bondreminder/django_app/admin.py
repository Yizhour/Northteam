from django.contrib import admin

from .models import BondReminderStore, BondReminderTableRow


@admin.register(BondReminderStore)
class BondReminderStoreAdmin(admin.ModelAdmin):
    list_display = ('key', 'updated_at')
    search_fields = ('key',)
    readonly_fields = ('updated_at',)


@admin.register(BondReminderTableRow)
class BondReminderTableRowAdmin(admin.ModelAdmin):
    list_display = ('table_key', 'row_index', 'updated_at')
    list_filter = ('table_key',)
    search_fields = ('table_key',)
    readonly_fields = ('created_at', 'updated_at')
