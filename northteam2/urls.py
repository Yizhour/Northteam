"""Root URL configuration for NorthTeam2."""

from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import include, path

from dashboard.admin_views import access_control
from dashboard.auth_views import WorkspaceLoginView

urlpatterns = [
    path('', include('dashboard.urls')),
    path('tools/bond-reminder/', include('tools.bondreminder.django_app.urls')),
    path('accounts/login/', WorkspaceLoginView.as_view(), name='login'),
    path('accounts/logout/', LogoutView.as_view(next_page='dashboard:home'), name='logout'),
    path('admin/access-control/', access_control, name='access_control'),
    path('admin/', admin.site.urls),
]

handler403 = 'dashboard.error_views.permission_denied'
