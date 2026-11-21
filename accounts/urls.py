from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.AppLoginView.as_view(), name='login'),
    path('register/', views.register, name='register'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('setup/', views.setup, name='setup'),
    path('forgot/', views.forgot, name='forgot'),
    path('reset/<uidb64>/<token>/', views.reset, name='reset'),
    path('password/', views.password_change, name='password_change'),
    path('', views.account_list, name='account_list'),
    path('<int:pk>/edit/', views.account_edit, name='account_edit'),
    path('<int:pk>/toggle/', views.account_toggle, name='account_toggle'),
    path('<int:pk>/delete/', views.account_delete, name='account_delete'),
    path('<int:pk>/reset-password/', views.account_reset_password, name='account_reset_password'),
    path('roles/', views.role_list, name='role_list'),
    path('roles/create/', views.role_create, name='role_create'),
    path('roles/<int:pk>/edit/', views.role_edit, name='role_edit'),
    path('roles/<int:pk>/delete/', views.role_delete, name='role_delete'),
    path('audit/', views.audit_log, name='audit_log'),
]
