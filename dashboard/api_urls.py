from django.urls import path

from . import api_views

urlpatterns = [
    path('session/', api_views.session_info, name='api_session'),
    path('login/', api_views.login_api, name='api_login'),
    path('logout/', api_views.logout_api, name='api_logout'),
    path('overview/', api_views.overview_api, name='api_overview'),
    path('tools/', api_views.tools_api, name='api_tools'),
    path('interns/', api_views.interns_api, name='api_interns'),
    path('interns/<int:intern_id>/', api_views.intern_detail_api, name='api_intern_detail'),
    path('intern-schedules/', api_views.intern_schedules_api, name='api_intern_schedules'),
    path('intern-schedules/<int:schedule_id>/', api_views.intern_schedule_detail_api, name='api_intern_schedule_detail'),
    path('intern-share/<str:token>/', api_views.intern_public_schedules_api, name='api_intern_public_schedules'),
    path('intern-share/<str:token>/schedules/<int:schedule_id>/', api_views.intern_public_schedule_detail_api, name='api_intern_public_schedule_detail'),
    path('pages/<slug:feature_key>/', api_views.page_api, name='api_page'),
]
