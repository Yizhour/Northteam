import sys

from django.apps import AppConfig


class BondReminderConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools.bondreminder.django_app'
    label = 'bondreminder'
    verbose_name = '付息兑付提醒'

    def ready(self):
        management_commands = {'migrate', 'makemigrations', 'collectstatic', 'test'}
        if any(command in sys.argv for command in management_commands):
            return

        from tools.bondreminder.app.config import SCHEDULER_ENABLED, ensure_directories
        from tools.bondreminder.app.scheduler import scheduler_service

        ensure_directories()
        if SCHEDULER_ENABLED:
            if not scheduler_service.start():
                scheduler_service.start_monitor()
