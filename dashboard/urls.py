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
    path('interns/script.js', views.interns_script, name='interns_script'),
    path('interns/share/<str:token>/', views.intern_share, name='intern_share'),
    path('market-yields/refresh/', views.market_yields_refresh, name='market_yields_refresh'),
    path('market-yields/status/', views.market_yields_status, name='market_yields_status'),
    path('common-websites/create/', views.common_website_create, name='common_website_create'),
    path('common-websites/<int:website_id>/update/', views.common_website_update, name='common_website_update'),
    path('common-websites/<int:website_id>/delete/', views.common_website_delete, name='common_website_delete'),
    path('common-websites/layout/', views.common_website_layout_update, name='common_website_layout_update'),
]
