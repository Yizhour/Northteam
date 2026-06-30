from django.urls import path

from .api import config, customer, data, pages, runs, tasks

urlpatterns = [
    path('', pages.index, name='bond_reminder'),
    path('static/<path:path>', pages.static_asset, name='bond_reminder_static'),
    path('api/health', pages.api_health, name='bond_reminder_health'),
    path('api/config', config.api_config, name='bond_reminder_config'),
    path('api/upload/bond-data', data.api_upload_bond_data, name='bond_reminder_upload_bond_data'),
    path('api/bond-preview', data.api_bond_preview, name='bond_reminder_bond_preview'),
    path('api/run/weekly', runs.api_run_weekly, name='bond_reminder_run_weekly'),
    path('api/run/daily', runs.api_run_daily, name='bond_reminder_run_daily'),
    path('api/run/manual', runs.api_run_manual, name='bond_reminder_run_manual'),
    path('api/contacts', config.api_contacts, name='bond_reminder_contacts'),
    path('api/tasks', tasks.api_tasks, name='bond_reminder_tasks'),
    path('api/tasks/<int:index>', tasks.api_task_detail, name='bond_reminder_task_detail'),
    path('api/tasks/<int:index>/toggle', tasks.api_task_toggle, name='bond_reminder_task_toggle'),
    path('api/tasks/<int:index>/run', tasks.api_task_run, name='bond_reminder_task_run'),
    path('api/logs', runs.api_logs, name='bond_reminder_logs'),
    path('api/customer-data', data.api_customer_data, name='bond_reminder_customer_data'),
    path('api/upload/customer-data', data.api_upload_customer_data, name='bond_reminder_upload_customer_data'),
    path('api/customer-settings', customer.api_customer_settings, name='bond_reminder_customer_settings'),
    path('api/customer/identity-ocr', customer.api_identity_ocr, name='bond_reminder_identity_ocr'),
    path('api/customer/birthday-check', customer.api_birthday_check, name='bond_reminder_birthday_check'),
]
