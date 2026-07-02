from django.apps import AppConfig


class ManuscriptReminderConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools.manuscriptreminder.django_app'
    label = 'manuscriptreminder'
    verbose_name = '底稿报送提醒'

    def ready(self):
        from tools.manuscriptreminder.app.config import SCHEDULER_ENABLED, ensure_directories

        ensure_directories()
        if SCHEDULER_ENABLED:
            from tools.manuscriptreminder.app.scheduler import scheduler_service

            scheduler_service.start_monitor()
