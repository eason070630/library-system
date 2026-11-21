from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=60, unique=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name
   


class Book(models.Model):
    """Minimal Book model so categories can be assigned.

    NOTE: the project's function table has no module that creates/edits books
    itself. Books are entered via the Django admin (or seed_demo command) for
    now. Whoever owns book records can extend this model (more fields, CRUD).
    """
    cover = models.ImageField(
        upload_to='book_covers/',
        blank=True,
        null=True
    )
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=120)
    isbn = models.CharField(max_length=13, unique=True)
    cover_image = models.ImageField(upload_to='book_covers/', blank=True, null=True)
    category = models.ForeignKey(
        Category, null=True, blank=True, on_delete=models.SET_NULL, related_name='books')

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title
    @property
    def is_borrowed(self):
        """Return True if this book currently has an active loan."""
        return self.loans.filter(status='active').exists()