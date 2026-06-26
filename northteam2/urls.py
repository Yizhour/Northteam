"""Root URL configuration for NorthTeam2."""

from django.contrib import admin
from django.urls import include, path, re_path

from .flask_mount import bond_reminder_view

urlpatterns = [
    path('', include('dashboard.urls')),
    path('tools/bond-reminder/', bond_reminder_view, {'path': ''}, name='bond_reminder'),
    re_path(r'^tools/bond-reminder/(?P<path>.*)$', bond_reminder_view, name='bond_reminder_path'),
    path('admin/', admin.site.urls),
]
