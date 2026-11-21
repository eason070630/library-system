from django.test import TestCase
from django.urls import reverse

from .models import Book, Category


class CategoryTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.client.force_login(get_user_model().objects.create_superuser('tester', 't@x.com', 'pw'))
        self.fic = Category.objects.create(name='Fiction')
        self.sci = Category.objects.create(name='Science')
        self.book = Book.objects.create(title='Dune', author='Frank Herbert', isbn='9780441172719')

    def test_add_valid_and_duplicate(self):
        r = self.client.post(reverse('categories:add'), {'name': 'History', 'description': ''}, follow=True)
        self.assertContains(r, 'added successfully')
        r = self.client.post(reverse('categories:add'), {'name': 'history', 'description': ''})
        self.assertContains(r, 'already exists')

    def test_add_invalid_name(self):
        r = self.client.post(reverse('categories:add'), {'name': '', 'description': ''})
        self.assertContains(r, 'required')
        r = self.client.post(reverse('categories:add'), {'name': '###', 'description': ''})
        self.assertContains(r, 'invalid characters')

    def test_edit(self):
        r = self.client.post(reverse('categories:edit', args=[self.fic.pk]),
                             {'name': 'Fiction & Fantasy', 'description': 'x'}, follow=True)
        self.assertContains(r, 'updated successfully')

    def test_assign_move_and_same_category(self):
        url = reverse('categories:assign')
        r = self.client.post(url, {'book': self.book.pk, 'category': self.fic.pk}, follow=True)
        self.assertContains(r, 'assigned to')
        r = self.client.post(url, {'book': self.book.pk, 'category': self.fic.pk})
        self.assertContains(r, 'already in')
        r = self.client.post(url, {'book': self.book.pk, 'category': self.sci.pk}, follow=True)
        self.assertContains(r, 'moved from')
        r = self.client.post(url, {})
        self.assertContains(r, 'select a book')

    def test_list_books_and_remove(self):
        self.book.category = self.fic; self.book.save()
        r = self.client.get(reverse('categories:books', args=[self.fic.pk]))
        self.assertContains(r, 'Dune')
        r = self.client.post(reverse('categories:remove_book', args=[self.sci.pk, self.book.pk]), follow=True)
        self.assertContains(r, 'does not belong')
        r = self.client.post(reverse('categories:remove_book', args=[self.fic.pk, self.book.pk]), follow=True)
        self.assertContains(r, 'removed from')
        self.book.refresh_from_db(); self.assertIsNone(self.book.category)

    def test_delete_blocked_when_books_then_allowed(self):
        self.book.category = self.fic; self.book.save()
        r = self.client.post(reverse('categories:delete', args=[self.fic.pk]), follow=True)
        self.assertContains(r, 'Cannot delete')
        self.assertTrue(Category.objects.filter(pk=self.fic.pk).exists())
        self.book.category = None; self.book.save()
        r = self.client.post(reverse('categories:delete', args=[self.fic.pk]), follow=True)
        self.assertContains(r, 'deleted successfully')


class BookAddTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.client.force_login(get_user_model().objects.create_superuser('tester', 't@x.com', 'pw'))

    def test_add_valid_and_invalid(self):
        url = reverse('categories:book_add')
        r = self.client.post(url, {'title': 'Dune', 'author': 'Frank Herbert', 'isbn': '978-0-441-17271-9'}, follow=True)
        self.assertContains(r, 'added successfully')
        self.assertEqual(Book.objects.get().isbn, '9780441172719')
        r = self.client.post(url, {'title': 'Dune 2', 'author': 'Frank Herbert', 'isbn': '9780441172719'})
        self.assertContains(r, 'already exists')
        r = self.client.post(url, {'title': 'X', 'author': '', 'isbn': '12ab'})
        self.assertContains(r, 'ISBN must be 10 or 13 digits')
        self.assertContains(r, 'required')
