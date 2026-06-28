"""Dashboard routes for the NorthTeam2 workspace."""

from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.home, name='home'),
    path('projects/', views.projects, name='projects'),
    path('tools/', views.tools, name='tools'),
    path('info/', views.info, name='info'),
    path('files/', views.files, name='files'),
    path('mistakes/', views.mistakes, name='mistakes'),
    path('interns/', views.interns, name='interns'),
    path('interns/share/<str:token>/', views.intern_share, name='intern_share'),
]
