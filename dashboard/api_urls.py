from django.urls import path

from . import api_views

urlpatterns = [
    path('session/', api_views.session_info, name='api_session'),
    path('login/', api_views.login_api, name='api_login'),
    path('logout/', api_views.logout_api, name='api_logout'),
    path('overview/', api_views.overview_api, name='api_overview'),
    path('tools/', api_views.tools_api, name='api_tools'),
    path('pages/<slug:feature_key>/', api_views.page_api, name='api_page'),
]
