"""Root URL configuration for NorthTeam2."""

from django.contrib import admin
from django.contrib.auth.views import LogoutView, PasswordChangeDoneView, PasswordChangeView
from django.urls import include, path, reverse_lazy

from dashboard.admin_views import access_control
from dashboard.auth_views import WorkspaceLoginView

urlpatterns = [
    path('api/', include('dashboard.api_urls')),
    path('', include('dashboard.urls')),
    path('tools/bond-reminder/', include('tools.bondreminder.django_app.urls')),
    path('accounts/login/', WorkspaceLoginView.as_view(), name='login'),
    path('accounts/logout/', LogoutView.as_view(next_page='login'), name='logout'),
    path(
        'accounts/password/change/',
        PasswordChangeView.as_view(success_url=reverse_lazy('password_change_done')),
        name='password_change',
    ),
    path(
        'accounts/password/change/done/',
        PasswordChangeDoneView.as_view(),
        name='password_change_done',
    ),
    path('admin/access-control/', access_control, name='access_control'),
    path('admin/', admin.site.urls),
]

handler403 = 'dashboard.error_views.permission_denied'
