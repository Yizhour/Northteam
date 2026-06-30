from django.urls import path

from .api import auth, interns, overview, tools

urlpatterns = [
    path('session/', auth.session_info, name='api_session'),
    path('login/', auth.login_api, name='api_login'),
    path('logout/', auth.logout_api, name='api_logout'),
    path('overview/', overview.overview_api, name='api_overview'),
    path('tools/', tools.tools_api, name='api_tools'),
    path('interns/', interns.interns_api, name='api_interns'),
    path('interns/<int:intern_id>/', interns.intern_detail_api, name='api_intern_detail'),
    path('intern-schedules/', interns.intern_schedules_api, name='api_intern_schedules'),
    path('intern-schedules/<int:schedule_id>/', interns.intern_schedule_detail_api, name='api_intern_schedule_detail'),
    path('intern-share/<str:token>/', interns.intern_public_schedules_api, name='api_intern_public_schedules'),
    path('intern-share/<str:token>/schedules/<int:schedule_id>/', interns.intern_public_schedule_detail_api, name='api_intern_public_schedule_detail'),
    path('pages/<slug:feature_key>/', overview.page_api, name='api_page'),
]
