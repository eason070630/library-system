from datetime import timedelta
from decimal import Decimal
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST
from accounts.audit import log_action
from categories.models import Book, Category
from members.models import Member
from .forms import CheckoutForm, RenewalForm, ReturnForm, FinePaymentForm, BorrowRequestForm
from .models import Loan, FinePayment, BorrowRequest


def active_loans(request):
    q = request.GET.get('q', '').strip()
    loans = Loan.objects.filter(status=Loan.ACTIVE).select_related('member', 'book').order_by('due_date')
    if q:
        loans = loans.filter(Q(member__name__icontains=q) | Q(member__email__icontains=q) |
                             Q(book__title__icontains=q) | Q(book__isbn__icontains=q))
    return render(request, 'borrowing/active_loans.html', {'loans': loans, 'q': q, 'today': timezone.localdate(),
                   'active_count': Loan.objects.filter(status=Loan.ACTIVE).count()})


def checkout(request):
    form = CheckoutForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        member, book = form.cleaned_data['member'], form.cleaned_data['book']
        with transaction.atomic():
            loan = Loan.objects.create(member=member, book=book,
                due_date=timezone.localdate() + timedelta(days=member.loan_days), created_by=request.user)
        log_action('loan_checkout', str(loan.pk), f'{member.name} checked out {book.title}', request=request)
        messages.success(request, f'"{book.title}" checked out to {member.name}. Due date: {loan.due_date:%d %b %Y}.')
        return redirect('borrowing:active_loans')
    return render(request, 'borrowing/form.html', {'form': form, 'title': 'Checkout Book',
                   'description': 'Issue an available book to an active member.'})


def renew(request):
    form = RenewalForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        loan = form.cleaned_data['loan']
        old_due = loan.due_date
        loan.due_date = max(loan.due_date, timezone.localdate()) + timedelta(days=loan.member.loan_days)
        loan.renewal_count += 1
        loan.save(update_fields=['due_date', 'renewal_count', 'updated_at'])
        log_action('loan_renew', str(loan.pk), f'{loan.book.title}: {old_due} -> {loan.due_date}', request=request)
        messages.success(request, f'Loan renewed. New due date: {loan.due_date:%d %b %Y}.')
        return redirect('borrowing:active_loans')
    return render(request, 'borrowing/form.html', {'form': form, 'title': 'Renew Loan',
                   'description': 'Each loan can be renewed once for the member’s membership loan period.'})


def history(request):
    q = request.GET.get('q', '').strip()
    loans = Loan.objects.select_related('member', 'book').prefetch_related('payments')
    if q:
        loans = loans.filter(Q(member__name__icontains=q) | Q(member__email__icontains=q) |
                             Q(book__title__icontains=q) | Q(book__isbn__icontains=q))
    return render(request, 'borrowing/history.html', {'loans': loans, 'q': q})


def process_return(request):
    form = ReturnForm(request.POST or None)
    preview = None
    if request.method == 'POST' and form.is_valid():
        loan = form.cleaned_data['loan']
        rate = form.cleaned_data['fine_per_day']
        today = timezone.localdate()
        days_late = max((today - loan.due_date).days, 0)
        preview = {'loan': loan, 'days_late': days_late, 'fine': (rate * days_late).quantize(Decimal('0.01'))}
        if request.POST.get('confirm_return') == 'yes':
            with transaction.atomic():
                loan.status = Loan.RETURNED
                loan.return_date = today
                loan.fine_amount = preview['fine']
                loan.returned_by = request.user
                loan.save(update_fields=['status', 'return_date', 'fine_amount', 'returned_by', 'updated_at'])
            log_action('book_return', str(loan.pk),
                       f'{loan.book.title} returned; {days_late} day(s) late; fine RM {loan.fine_amount}', request=request)
            messages.success(request, f'Book returned. Late days: {days_late}. Fine: RM {loan.fine_amount:.2f}.')
            return redirect('borrowing:history')
    return render(request, 'borrowing/return.html', {'form': form, 'preview': preview})


def record_payment(request):
    form = FinePaymentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        payment = form.save(commit=False)
        payment.received_by = request.user
        payment.save()
        log_action('fine_payment', str(payment.pk),
                   f'Loan #{payment.loan_id}: RM {payment.amount} via {payment.get_method_display()}', request=request)
        messages.success(request, f'Fine payment of RM {payment.amount:.2f} recorded. Remaining: RM {payment.loan.outstanding_fine:.2f}.')
        return redirect('borrowing:history')
    return render(request, 'borrowing/form.html', {'form': form, 'title': 'Record Fine Payment',
                   'description': 'Record a full or partial payment against an outstanding returned-book fine.'})


def fine_report(request):
    start = request.GET.get('start', '').strip()
    end = request.GET.get('end', '').strip()
    start_date, end_date = (parse_date(start) if start else None), (parse_date(end) if end else None)
    if start and not start_date:
        messages.error(request, 'Please enter a valid start date.')
        start = ''
    if end and not end_date:
        messages.error(request, 'Please enter a valid end date.')
        end = ''
    if start_date and end_date and start_date > end_date:
        messages.error(request, 'The start date cannot be later than the end date.')
        start = end = ''
        start_date = end_date = None
    payments = FinePayment.objects.select_related('loan__member', 'loan__book', 'received_by')
    loans = Loan.objects.filter(status=Loan.RETURNED, fine_amount__gt=0).select_related('member', 'book').prefetch_related('payments')
    if start_date:
        payments = payments.filter(paid_at__date__gte=start_date)
        loans = loans.filter(return_date__gte=start_date)
    if end_date:
        payments = payments.filter(paid_at__date__lte=end_date)
        loans = loans.filter(return_date__lte=end_date)
    totals = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    outstanding = sum((loan.outstanding_fine for loan in loans), Decimal('0.00'))
    return render(request, 'borrowing/fine_report.html', {'payments': payments, 'loans': loans,
                   'start': start, 'end': end, 'total_paid': totals, 'outstanding': outstanding,
                   'total_fines': loans.aggregate(total=Sum('fine_amount'))['total'] or Decimal('0.00')})


def _current_member(request):
    return get_object_or_404(Member.objects.select_related('membership_type'), user=request.user)



def member_borrow(request):
    """Member self-service: browse books and submit a borrowing request."""

    member = _current_member(request)

    # Display all books on the borrowing page
    books = Book.objects.all().order_by('title')
    categories = Category.objects.all().order_by('name')
    if request.method == 'POST':
        form = BorrowRequestForm(request.POST)

        if form.is_valid():
            book = form.cleaned_data['book']

            if not member.can_borrow():
                form.add_error(
                    None,
                    'Your membership is inactive or you have reached your borrowing limit.'
                )

            elif BorrowRequest.objects.filter(
                member=member,
                book=book,
                status=BorrowRequest.PENDING
            ).exists():
                form.add_error(
                    'book',
                    'You already have a pending request for this book.'
                )

            else:
                BorrowRequest.objects.create(
                    member=member,
                    book=book
                )

                messages.success(
                    request,
                    f'Your request for "{book.title}" was submitted. '
                    'A librarian must approve it before checkout.'
                )

                return redirect('borrowing:my_loans')

        selected_book_id = request.POST.get('book', '')

    else:
        form = BorrowRequestForm()
        selected_book_id = request.GET.get('book', '')

    return render(request, 'borrowing/member_borrow.html', {
        'form': form,
        'member': member,
        'books': books,
        'categories': categories,
        'selected_book_id': selected_book_id,
    })



def my_loans(request):
    member = _current_member(request)
    loans = Loan.objects.filter(member=member).select_related('book').prefetch_related('payments')
    requests = BorrowRequest.objects.filter(member=member).select_related('book')
    return render(request, 'borrowing/my_loans.html', {'member': member, 'loans': loans, 'requests': requests})


def request_list(request):
    requests = BorrowRequest.objects.select_related('member', 'book', 'reviewed_by').all()
    status = request.GET.get('status', BorrowRequest.PENDING)
    if status in {BorrowRequest.PENDING, BorrowRequest.APPROVED, BorrowRequest.REJECTED}:
        requests = requests.filter(status=status)
    else:
        status = ''
    return render(request, 'borrowing/request_list.html', {'requests': requests, 'status': status})


@require_POST
def review_request(request, pk):
    with transaction.atomic():
        borrow_request = get_object_or_404(BorrowRequest.objects.select_for_update().select_related('member', 'book'), pk=pk)
        if borrow_request.status != BorrowRequest.PENDING:
            messages.warning(request, 'This request has already been reviewed.')
            return redirect('borrowing:request_list')
        action = request.POST.get('action')
        note = request.POST.get('review_note', '').strip()[:255]
        if action == 'approve':
            member, book = borrow_request.member, borrow_request.book
            if not member.can_borrow():
                messages.error(request, 'Cannot approve: member is inactive or has reached the borrowing limit.')
                return redirect('borrowing:request_list')
            if Loan.objects.filter(book=book, status=Loan.ACTIVE).exists():
                messages.error(request, 'Cannot approve: this book is already checked out.')
                return redirect('borrowing:request_list')
            loan = Loan.objects.create(member=member, book=book,
                due_date=timezone.localdate() + timedelta(days=member.loan_days), created_by=request.user)
            borrow_request.status = BorrowRequest.APPROVED
            borrow_request.loan = loan
            borrow_request.review_note = note
            borrow_request.reviewed_by = request.user
            borrow_request.reviewed_at = timezone.now()
            borrow_request.save(update_fields=['status', 'loan', 'review_note', 'reviewed_by', 'reviewed_at'])
            log_action('borrow_request_approved', str(borrow_request.pk),
                       f'{member.name}: {book.title}; loan #{loan.pk}', request=request)
            messages.success(request, f'Request approved. Loan created; due date {loan.due_date:%d %b %Y}.')
        elif action == 'reject':
            borrow_request.status = BorrowRequest.REJECTED
            borrow_request.review_note = note
            borrow_request.reviewed_by = request.user
            borrow_request.reviewed_at = timezone.now()
            borrow_request.save(update_fields=['status', 'review_note', 'reviewed_by', 'reviewed_at'])
            log_action('borrow_request_rejected', str(borrow_request.pk),
                       f'{borrow_request.member.name}: {borrow_request.book.title}', request=request)
            messages.success(request, 'Borrow request rejected.')
        else:
            messages.error(request, 'Invalid review action.')
    return redirect('borrowing:request_list')
