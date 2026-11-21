from django.urls import path

from . import views

app_name = 'members'

urlpatterns = [
    path('', views.member_list, name='list'),
    path('register/', views.member_register, name='register'),
    path('<int:pk>/edit/', views.member_update, name='update'),
    path('<int:pk>/history/', views.member_history, name='history'),
    path('<int:pk>/deactivate/', views.member_deactivate, name='deactivate'),
    path('<int:pk>/reactivate/', views.member_reactivate, name='reactivate'),
    path('<int:pk>/delete/', views.member_delete, name='delete'),
    path('profile/', views.member_profile, name='profile'),
]
