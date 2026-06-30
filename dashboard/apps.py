from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dashboard'
    verbose_name = '工作台'

    def ready(self):
        from dashboard.services.market_yield_scheduler import (
            market_yield_scheduler,
            should_start_market_yield_scheduler,
        )

        if should_start_market_yield_scheduler():
            if not market_yield_scheduler.start():
                market_yield_scheduler.start_monitor()
