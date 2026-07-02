from django.contrib import admin

from .models import ManuscriptReminderLog, ManuscriptReminderStore, ManuscriptReminderTableRow


@admin.register(ManuscriptReminderStore)
class ManuscriptReminderStoreAdmin(admin.ModelAdmin):
    list_display = ('key', 'updated_at')
    search_fields = ('key',)
    readonly_fields = ('updated_at',)


@admin.register(ManuscriptReminderTableRow)
class ManuscriptReminderTableRowAdmin(admin.ModelAdmin):
    list_display = ('row_index', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ManuscriptReminderLog)
class ManuscriptReminderLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'line')
    readonly_fields = ('created_at',)
