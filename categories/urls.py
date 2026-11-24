from django.urls import path
from . import views

app_name = 'categories'

urlpatterns = [
    path('', views.category_list, name='list'),

    # Member Browse Books
    path('browse/', views.member_browse_books, name='member_browse'),

    # Book Management
    path('manage-books/', views.manage_books, name='manage_books'),
    path('books/<int:pk>/edit/', views.book_edit, name='book_edit'),
    path('books/<int:pk>/delete/', views.book_delete, name='book_delete'),

    path('add/', views.category_add, name='add'),
    path('books/add/', views.book_add, name='book_add'),
    path('assign/', views.assign_book, name='assign'),
    path('<int:pk>/edit/', views.category_edit, name='edit'),
    path('<int:pk>/delete/', views.category_delete, name='delete'),
    path('<int:pk>/books/', views.books_by_category, name='books'),
    path('<int:pk>/books/<int:book_id>/remove/', views.category_remove_book, name='remove_book'),
]