from django.urls import path

from . import views

app_name = 'appointments'

urlpatterns = [
    path('', views.upcoming, name='upcoming'),
    path('schedule/', views.schedule, name='schedule'),
    path('<int:pk>/cancel/', views.cancel, name='cancel'),
    path('<int:pk>/delete/', views.appointment_delete, name='delete'),
    path('slots/', views.slot_list, name='slot_list'),
    path('slots/add/', views.slot_add, name='slot_add'),
    path('slots/<int:pk>/edit/', views.slot_edit, name='slot_edit'),
    path('slots/<int:pk>/toggle/', views.slot_toggle, name='slot_toggle'),
    path('my-appointments/', views.my_appointments, name='my_appointments'),
    path('slots/<int:pk>/delete/', views.slot_delete, name='slot_delete'),
]
