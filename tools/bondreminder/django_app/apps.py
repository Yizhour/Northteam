from django.apps import AppConfig


class BondReminderConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools.bondreminder.django_app'
    verbose_name = '付息兑付提醒'

    def ready(self):
        from tools.bondreminder.app.config import SCHEDULER_ENABLED, ensure_directories
        from tools.bondreminder.app.scheduler import scheduler_service

        ensure_directories()
        if SCHEDULER_ENABLED:
            scheduler_service.start()
