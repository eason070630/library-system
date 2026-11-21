import re

from django import forms

from library_system.formstyle import BootstrapFormMixin

from .models import Book, Category

CAT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\s&'\-/]*$")


class CategoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description']

    def clean_name(self):
        name = ' '.join(self.cleaned_data['name'].split())
        if len(name) < 2:
            raise forms.ValidationError('Category name must be at least 2 characters.')
        if not CAT_NAME_RE.match(name):
            raise forms.ValidationError('Category name contains invalid characters.')
        qs = Category.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A category with this name already exists.')
        return name


class AssignForm(BootstrapFormMixin, forms.Form):
    book = forms.ModelChoiceField(
        queryset=Book.objects.all(), empty_label='-- Select a book --',
        error_messages={'required': 'Please select a book.',
                        'invalid_choice': 'Selected book does not exist.'})
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(), empty_label='-- Select a category --',
        error_messages={'required': 'Please select a category.',
                        'invalid_choice': 'Selected category does not exist.'})

    def clean(self):
        data = super().clean()
        book, category = data.get('book'), data.get('category')
        if book and category and book.category_id == category.pk:
            raise forms.ValidationError(f'"{book.title}" is already in "{category.name}".')
        return data


class BookForm(BootstrapFormMixin, forms.ModelForm):
    """Helper form for adding books (not part of the graded function table)."""

    # Allow hyphens/spaces when typing; they are stripped in clean_isbn.
    isbn = forms.CharField(max_length=20, label='ISBN')

    class Meta:
        model = Book
        fields = ['title', 'author', 'isbn', 'category', 'cover_image']

    def clean_title(self):
        title = ' '.join(self.cleaned_data['title'].split())
        if len(title) < 2:
            raise forms.ValidationError('Title must be at least 2 characters.')
        return title

    def clean_author(self):
        author = ' '.join(self.cleaned_data['author'].split())
        if len(author) < 2:
            raise forms.ValidationError('Author must be at least 2 characters.')
        return author

    def clean_isbn(self):
        isbn = re.sub(r'[\s\-]', '', self.cleaned_data['isbn'])
        if not re.fullmatch(r'\d{10}|\d{13}', isbn):
            raise forms.ValidationError('ISBN must be 10 or 13 digits.')
        if Book.objects.filter(isbn=isbn).exists():
            raise forms.ValidationError('A book with this ISBN already exists.')
        return isbn
