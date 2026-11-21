from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone


class Loan(models.Model):
    ACTIVE = 'active'
    RETURNED = 'returned'
    STATUS_CHOICES = [(ACTIVE, 'Active'), (RETURNED, 'Returned')]

    member = models.ForeignKey('members.Member', on_delete=models.PROTECT, related_name='loans')
    book = models.ForeignKey('categories.Book', on_delete=models.PROTECT, related_name='loans')
    checkout_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField()
    return_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=ACTIVE)
    renewal_count = models.PositiveSmallIntegerField(default=0)
    fine_amount = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='created_loans')
    returned_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='returned_loans')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-checkout_date', '-pk']
        constraints = [
            models.UniqueConstraint(fields=['book'], condition=models.Q(status='active'),
                                    name='one_active_loan_per_book')
        ]

    def __str__(self):
        return f'{self.book.title} — {self.member.name}'

    @property
    def overdue_days(self):
        end_date = self.return_date or timezone.localdate()
        return max((end_date - self.due_date).days, 0)

    @property
    def amount_paid(self):
        return self.payments.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    @property
    def outstanding_fine(self):
        return max(self.fine_amount - self.amount_paid, Decimal('0.00'))

    @property
    def fine_status(self):
        if self.fine_amount <= 0:
            return 'No fine'
        if self.outstanding_fine <= 0:
            return 'Paid'
        if self.amount_paid > 0:
            return 'Partially paid'
        return 'Unpaid'


class FinePayment(models.Model):
    CASH = 'cash'
    CARD = 'card'
    ONLINE = 'online'
    PAYMENT_METHODS = [(CASH, 'Cash'), (CARD, 'Card'), (ONLINE, 'Online transfer')]

    loan = models.ForeignKey(Loan, on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    method = models.CharField(max_length=10, choices=PAYMENT_METHODS, default=CASH)
    reference = models.CharField(max_length=80, blank=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='fine_payments_received')
    paid_at = models.DateTimeField(default=timezone.now)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-paid_at', '-pk']

    def __str__(self):
        return f'Fine payment #{self.pk} - RM {self.amount}'


class BorrowRequest(models.Model):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    STATUS_CHOICES = [(PENDING, 'Pending'), (APPROVED, 'Approved'), (REJECTED, 'Rejected')]

    member = models.ForeignKey('members.Member', on_delete=models.PROTECT, related_name='borrow_requests')
    book = models.ForeignKey('categories.Book', on_delete=models.PROTECT, related_name='borrow_requests')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='reviewed_borrow_requests')
    review_note = models.CharField(max_length=255, blank=True)
    loan = models.OneToOneField(Loan, null=True, blank=True, on_delete=models.SET_NULL, related_name='borrow_request')

    class Meta:
        ordering = ['-requested_at', '-pk']

    def __str__(self):
        return f'{self.member.name} - {self.book.title} ({self.status})'
