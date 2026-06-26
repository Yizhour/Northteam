"""Dashboard routes for the NorthTeam2 workspace."""

from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.home, name='home'),
    path('projects/', views.placeholder, {'page_title': '项目空间'}, name='projects'),
    path('tools/', views.tools, name='tools'),
    path('info/', views.placeholder, {'page_title': '常用信息'}, name='info'),
    path('files/', views.placeholder, {'page_title': '文件共享空间'}, name='files'),
    path('mistakes/', views.placeholder, {'page_title': '错题本'}, name='mistakes'),
    path('interns/', views.placeholder, {'page_title': '实习生登记'}, name='interns'),
]
