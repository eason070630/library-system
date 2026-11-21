from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import Book
from .forms import AssignForm, BookForm, CategoryForm
from .models import Book, Category


def category_list(request):
    categories = Category.objects.annotate(book_count=Count('books'))
    return render(request, 'categories/list.html', {'categories': categories})


def category_add(request):
    """Add New Category (Create)."""
    form = CategoryForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST':
        if form.is_valid():
            cat = form.save()
            messages.success(request, f'Category "{cat.name}" added successfully.')
            return redirect('categories:list')
        messages.error(request, 'Could not add category. Please correct the errors below.')
    return render(request, 'categories/form.html', {'form': form, 'title': 'Add New Category'})


def category_edit(request, pk):
    """Edit Category Details (Update). Also lets the user remove books from
    the category and delete the category from this page."""
    category = get_object_or_404(Category, pk=pk)
    form = CategoryForm(request.POST if request.method == 'POST' else None, instance=category)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, f'Category "{category.name}" updated successfully.')
            return redirect('categories:list')
        messages.error(request, 'Update failed. Please correct the errors below.')
    return render(request, 'categories/edit.html', {
        'form': form, 'category': category, 'books': category.books.all()})


@require_POST
def category_remove_book(request, pk, book_id):
    """Remove a book from a category (book becomes uncategorised)."""
    category = get_object_or_404(Category, pk=pk)
    book = get_object_or_404(Book, pk=book_id)
    if book.category_id != category.pk:
        messages.error(request, f'"{book.title}" does not belong to "{category.name}".')
    else:
        book.category = None
        book.save(update_fields=['category'])
        messages.success(request, f'"{book.title}" removed from "{category.name}".')
    return redirect('categories:edit', pk=category.pk)


def category_delete(request, pk):
    """Delete Category: blocked while books are still assigned."""
    category = get_object_or_404(Category, pk=pk)
    count = category.books.count()
    if count:
        messages.error(
            request, f'Cannot delete "{category.name}": it still has {count} book(s). '
                     'Remove or reassign them first.')
        return redirect('categories:edit', pk=category.pk)
    if request.method == 'POST':
        name = category.name
        category.delete()
        messages.success(request, f'Category "{name}" deleted successfully.')
        return redirect('categories:list')
    return render(request, 'categories/confirm_delete.html', {'category': category})


def assign_book(request):
    """Assign Book to Category."""
    form = AssignForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST':
        if form.is_valid():
            book, cat = form.cleaned_data['book'], form.cleaned_data['category']
            old = book.category
            book.category = cat
            book.save(update_fields=['category'])
            if old:
                messages.success(request, f'"{book.title}" moved from "{old.name}" to "{cat.name}".')
            else:
                messages.success(request, f'"{book.title}" assigned to "{cat.name}".')
            return redirect('categories:books', pk=cat.pk)
        messages.error(request, 'Assignment failed. Please correct the errors below.')
    return render(request, 'categories/assign.html', {'form': form})


def books_by_category(request, pk):
    """List Books by Category."""
    category = get_object_or_404(Category, pk=pk)
    return render(request, 'categories/books.html', {
        'category': category, 'books': category.books.all()})


def book_add(request):
    """Add Book (helper page so books exist to assign to categories)."""
    form = BookForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST':
        if form.is_valid():
            book = form.save()
            messages.success(request, f'Book "{book.title}" added successfully.')
            return redirect('categories:book_add')
        messages.error(request, 'Could not add book. Please correct the errors below.')
    recent = Book.objects.order_by('-pk')[:10]
    return render(request, 'categories/book_form.html', {'form': form, 'recent': recent})
@login_required
def member_browse_books(request):
    """Read-only book browsing page for logged-in members."""
    books = Book.objects.select_related('category').order_by('title')

    return render(request, 'categories/member_books.html', {
        'books': books,
    })
