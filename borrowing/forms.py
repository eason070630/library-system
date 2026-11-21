from decimal import Decimal
from django import forms
from django.utils import timezone
from library_system.formstyle import BootstrapFormMixin
from members.models import Member
from categories.models import Book
from .models import Loan, FinePayment


class CheckoutForm(BootstrapFormMixin, forms.Form):
    member = forms.ModelChoiceField(queryset=Member.objects.none(), empty_label='-- Select member --')
    book = forms.ModelChoiceField(queryset=Book.objects.none(), empty_label='-- Select available book --')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['member'].queryset = Member.objects.filter(status=Member.ACTIVE).select_related('membership_type')
        self.fields['book'].queryset = Book.objects.exclude(loans__status=Loan.ACTIVE).order_by('title')

    def clean(self):
        data = super().clean()
        member, book = data.get('member'), data.get('book')
        if member and not member.can_borrow():
            self.add_error('member', 'This member is inactive or has reached the borrowing limit for their membership tier.')
        if book and Loan.objects.filter(book=book, status=Loan.ACTIVE).exists():
            self.add_error('book', 'This book is currently checked out.')
        return data


class RenewalForm(BootstrapFormMixin, forms.Form):
    loan = forms.ModelChoiceField(queryset=Loan.objects.none(), empty_label='-- Select active loan --')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['loan'].queryset = Loan.objects.filter(status=Loan.ACTIVE).select_related('member', 'book')

    def clean_loan(self):
        loan = self.cleaned_data['loan']
        if loan.renewal_count >= 1:
            raise forms.ValidationError('This loan has already been renewed once.')
        return loan


class ReturnForm(BootstrapFormMixin, forms.Form):
    loan = forms.ModelChoiceField(queryset=Loan.objects.none(), empty_label='-- Select active loan --')
    fine_per_day = forms.DecimalField(min_value=Decimal('0.00'), max_digits=6, decimal_places=2,
                                      initial=Decimal('1.00'), label='Fine per overdue day (RM)')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['loan'].queryset = Loan.objects.filter(status=Loan.ACTIVE).select_related('member', 'book')


class FinePaymentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = FinePayment
        fields = ['loan', 'amount', 'method', 'reference', 'note']
        widgets = {'note': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['loan'].queryset = Loan.objects.filter(status=Loan.RETURNED, fine_amount__gt=0).select_related('member', 'book')

    def clean(self):
        data = super().clean()
        loan, amount = data.get('loan'), data.get('amount')
        if loan and amount is not None:
            if amount <= 0:
                self.add_error('amount', 'Payment amount must be greater than zero.')
            elif amount > loan.outstanding_fine:
                self.add_error('amount', f'Payment cannot exceed the outstanding fine of RM {loan.outstanding_fine:.2f}.')
        return data


class BorrowRequestForm(BootstrapFormMixin, forms.Form):
    book = forms.ModelChoiceField(
        queryset=Book.objects.none(),
        empty_label='-- Select an available book --'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['book'].queryset = (
            Book.objects
            .exclude(loans__status=Loan.ACTIVE)
            .distinct()
            .order_by('title')
        )

    def clean_book(self):
        book = self.cleaned_data['book']

        if Loan.objects.filter(
            book=book,
            status=Loan.ACTIVE
        ).exists():
            raise forms.ValidationError(
                'This book is currently checked out.'
            )

        return book