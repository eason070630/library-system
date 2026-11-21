from django.urls import path
from . import views

app_name = 'borrowing'
urlpatterns = [
    path('', views.active_loans, name='active_loans'),
    path('checkout/', views.checkout, name='checkout'),
    path('renew/', views.renew, name='renew'),
    path('history/', views.history, name='history'),
    path('return/', views.process_return, name='return'),
    path('fine-payment/', views.record_payment, name='fine_payment'),
    path('fine-report/', views.fine_report, name='fine_report'),
    path('my/borrow/', views.member_borrow, name='member_borrow'),
    path('my/loans/', views.my_loans, name='my_loans'),
    path('requests/', views.request_list, name='request_list'),
    path('requests/<int:pk>/review/', views.review_request, name='review_request'),
]
