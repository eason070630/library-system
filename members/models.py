from django.apps import apps
from django.conf import settings
from django.db import models


class MembershipType(models.Model):
    """Membership tier. Higher tiers can borrow more books for longer."""
    name = models.CharField(max_length=30, unique=True)
    level = models.PositiveSmallIntegerField(unique=True, help_text='1 = lowest tier')
    max_books = models.PositiveSmallIntegerField(help_text='Max books borrowed at the same time')
    loan_days = models.PositiveSmallIntegerField(help_text='Days allowed per loan')
    description = models.CharField(max_length=150, blank=True)
    badge_color = models.CharField(max_length=20, default='secondary',
                                   help_text='Bootstrap colour name, e.g. secondary, primary, warning')

    class Meta:
        ordering = ['level']

    def __str__(self):
        return self.name


class Member(models.Model):
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    STATUS_CHOICES = [(ACTIVE, 'Active'), (INACTIVE, 'Inactive')]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True,
                                on_delete=models.SET_NULL, related_name='library_member')
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15)
    address = models.CharField(max_length=255, blank=True)
    join_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=ACTIVE)
    membership_type = models.ForeignKey(
        MembershipType, on_delete=models.PROTECT, related_name='members')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.email})'

    @property
    def is_active(self):
        return self.status == self.ACTIVE

    # ---- Integration with Student 2's Borrowing module -------------------
    # Assumption: Student 2's app is called "borrowing", with a model "Loan"
    # that has a ForeignKey "member" -> members.Member and a "status" field
    # whose value 'returned' means the book is back. Adjust the names below
    # once Student 2 confirms their model.
    @staticmethod
    def _loan_model():
        try:
            return apps.get_model('borrowing', 'Loan')
        except LookupError:
            return None

    def loan_history(self):
        Loan = self._loan_model()
        return Loan.objects.filter(member=self) if Loan else None

    def has_unreturned_loans(self):
        Loan = self._loan_model()
        if Loan is None:
            return False
        return Loan.objects.filter(member=self).exclude(status='returned').exists()

    def has_any_loans(self):
        Loan = self._loan_model()
        return bool(Loan and Loan.objects.filter(member=self).exists())

    # ---- Borrowing limits (read by Student 2's Borrowing module) ----------
    @property
    def max_books(self):
        return self.membership_type.max_books

    @property
    def loan_days(self):
        return self.membership_type.loan_days

    def active_loan_count(self):
        Loan = self._loan_model()
        if Loan is None:
            return 0
        return Loan.objects.filter(member=self).exclude(status='returned').count()

    def remaining_quota(self):
        """How many more books this member may borrow right now."""
        return max(self.max_books - self.active_loan_count(), 0)

    def can_borrow(self):
        return self.is_active and self.remaining_quota() > 0

    # ---- Integration with the Appointment module ---------------------------
    def has_appointments(self):
        return hasattr(self, 'appointments') and self.appointments.exists()

    def has_upcoming_appointments(self):
        if not hasattr(self, 'appointments'):
            return False
        return any(a.is_upcoming for a in self.appointments.select_related('slot'))
