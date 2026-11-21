from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from categories.models import Book, Category
from members.models import Member, MembershipType
from .models import Loan, FinePayment


class BorrowingModelTests(TestCase):
    def setUp(self):
        self.tier = MembershipType.objects.create(name='Test', level=99, max_books=2, loan_days=14)
        self.member = Member.objects.create(name='Test Member', email='member@example.com',
            phone='0123456789', membership_type=self.tier)
        self.category = Category.objects.create(name='Test Category')
        self.book = Book.objects.create(title='Test Book', author='Test Author', isbn='1234567890', category=self.category)
        self.user = get_user_model().objects.create_user(username='staff', password='test-password')

    def test_checkout_and_return_fine(self):
        due = timezone.localdate() - timedelta(days=3)
        loan = Loan.objects.create(member=self.member, book=self.book, due_date=due, created_by=self.user)
        loan.status = Loan.RETURNED
        loan.return_date = timezone.localdate()
        loan.fine_amount = Decimal('3.00')
        loan.returned_by = self.user
        loan.save()
        self.assertEqual(loan.overdue_days, 3)
        self.assertEqual(loan.outstanding_fine, Decimal('3.00'))

    def test_partial_fine_payment(self):
        loan = Loan.objects.create(member=self.member, book=self.book,
            due_date=timezone.localdate() - timedelta(days=2), status=Loan.RETURNED,
            return_date=timezone.localdate(), fine_amount=Decimal('2.00'))
        FinePayment.objects.create(loan=loan, amount=Decimal('1.00'), received_by=self.user)
        self.assertEqual(loan.amount_paid, Decimal('1.00'))
        self.assertEqual(loan.outstanding_fine, Decimal('1.00'))
        self.assertEqual(loan.fine_status, 'Partially paid')
