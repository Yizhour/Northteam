from django.urls import path

from .api import config, data, pages, runs

urlpatterns = [
    path('', pages.index, name='manuscript_reminder'),
    path('static/<path:path>', pages.static_asset, name='manuscript_reminder_static'),
    path('api/config', config.api_config, name='manuscript_reminder_config'),
    path('api/upload/data', data.api_upload_data, name='manuscript_reminder_upload_data'),
    path('api/preview', data.api_preview, name='manuscript_reminder_preview'),
    path('api/overview', data.api_overview, name='manuscript_reminder_overview'),
    path('api/run/weekly', runs.api_run_weekly, name='manuscript_reminder_run_weekly'),
    path('api/run/daily', runs.api_run_daily, name='manuscript_reminder_run_daily'),
    path('api/run/manual', runs.api_run_manual, name='manuscript_reminder_run_manual'),
    path('api/logs', runs.api_logs, name='manuscript_reminder_logs'),
]
