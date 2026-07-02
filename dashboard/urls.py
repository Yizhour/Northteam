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
    path('market-yields/public/', views.market_yields_public, name='market_yields_public'),
    path('market-yields/public/status/', views.market_yields_public_status, name='market_yields_public_status'),
    path('info/cards/create/', views.info_card_create, name='info_card_create'),
    path('info/cards/<int:card_id>/update/', views.info_card_update, name='info_card_update'),
    path('info/cards/<int:card_id>/delete/', views.info_card_delete, name='info_card_delete'),
    path('info/cards/order/', views.info_card_order_update, name='info_card_order_update'),
    path('info/cards/layout/', views.info_card_layout_update, name='info_card_layout_update'),
    path('common-websites/create/', views.common_website_create, name='common_website_create'),
    path('common-websites/<int:website_id>/update/', views.common_website_update, name='common_website_update'),
    path('common-websites/<int:website_id>/delete/', views.common_website_delete, name='common_website_delete'),
    path('common-websites/layout/', views.common_website_layout_update, name='common_website_layout_update'),
    path('common-websites/save/', views.common_website_bulk_update, name='common_website_bulk_update'),
]
