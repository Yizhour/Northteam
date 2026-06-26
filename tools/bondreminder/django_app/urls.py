from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='bond_reminder'),
    path('static/<path:path>', views.static_asset, name='bond_reminder_static'),
    path('api/health', views.api_health, name='bond_reminder_health'),
    path('api/config', views.api_config, name='bond_reminder_config'),
    path('api/upload/bond-data', views.api_upload_bond_data, name='bond_reminder_upload_bond_data'),
    path('api/bond-preview', views.api_bond_preview, name='bond_reminder_bond_preview'),
    path('api/run/weekly', views.api_run_weekly, name='bond_reminder_run_weekly'),
    path('api/run/daily', views.api_run_daily, name='bond_reminder_run_daily'),
    path('api/run/manual', views.api_run_manual, name='bond_reminder_run_manual'),
    path('api/contacts', views.api_contacts, name='bond_reminder_contacts'),
    path('api/tasks', views.api_tasks, name='bond_reminder_tasks'),
    path('api/tasks/<int:index>', views.api_task_detail, name='bond_reminder_task_detail'),
    path('api/tasks/<int:index>/toggle', views.api_task_toggle, name='bond_reminder_task_toggle'),
    path('api/tasks/<int:index>/run', views.api_task_run, name='bond_reminder_task_run'),
    path('api/logs', views.api_logs, name='bond_reminder_logs'),
    path('api/customer-data', views.api_customer_data, name='bond_reminder_customer_data'),
    path('api/upload/customer-data', views.api_upload_customer_data, name='bond_reminder_upload_customer_data'),
    path('api/customer-settings', views.api_customer_settings, name='bond_reminder_customer_settings'),
    path('api/customer/identity-ocr', views.api_identity_ocr, name='bond_reminder_identity_ocr'),
    path('api/customer/birthday-check', views.api_birthday_check, name='bond_reminder_birthday_check'),
]
