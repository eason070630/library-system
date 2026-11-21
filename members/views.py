from django.contrib import messages
from django.db.models import Count, Q
from django.db import transaction
from django.utils.text import slugify
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from datetime import timedelta

from django.utils import timezone

from .forms import MemberForm, MemberProfileForm
from categories.models import Book, Category

from .models import Member, MembershipType
from django.contrib.auth import get_user_model

from accounts.models import AuditLog, Role
from accounts.rights import has_right
from appointments.models import Appointment
from django.contrib.auth.decorators import login_required
from django.db import transaction
from .forms import MemberForm, MemberProfileForm

@login_required
def member_profile(request):
    member = get_object_or_404(
        Member,
        user=request.user
    )

    form = MemberProfileForm(
        request.POST if request.method == 'POST' else None,
        instance=member
    )

    if request.method == 'POST':
        if form.is_valid():
            with transaction.atomic():
                member = form.save()

                request.user.username = form.cleaned_data['username']
                request.user.email = member.email
                request.user.save(
                    update_fields=['username', 'email']
                )

            messages.success(
                request,
                'Your profile has been updated successfully.'
            )
            return redirect('members:profile')

    return render(request, 'members/member_profile.html', {
        'member': member,
        'form': form,
    })

def member_list(request):
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    members = Member.objects.all()
    if q:
        members = members.filter(Q(name__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q))
    if status in (Member.ACTIVE, Member.INACTIVE):
        members = members.filter(status=status)
    tier = request.GET.get('tier', '')
    if tier.isdigit():
        members = members.filter(membership_type_id=int(tier))
    members = members.select_related('membership_type')
    return render(request, 'members/list.html', {
        'members': members, 'q': q, 'status': status, 'tier': tier,
        'tiers': MembershipType.objects.all()})


def member_register(request):
    """Register a member profile and its login account in one step."""
    form = MemberForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST':
        if form.is_valid():
            data = form.cleaned_data
            # Derive a login username from the email prefix, adding a suffix if needed.
            base = slugify(data['email'].split('@', 1)[0])[:25] or 'member'
            username = base
            suffix = 1
            User = get_user_model()
            while User.objects.filter(username__iexact=username).exists():
                username = f'{base[:25-len(str(suffix))-1]}_{suffix}'
                suffix += 1
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username, email=data['email'],
                    password=data['password1'], first_name=data['name'])
                member = form.save(commit=False)
                member.user = user
                member.save()
            messages.success(
                request,
                f'Member "{member.name}" registered. Login username: {username}. '
                'The member can sign in using this username and the password you set.')
            return redirect('members:list')
        messages.error(request, 'Registration failed. Please correct the errors below.')
    return render(request, 'members/form.html', {'form': form, 'title': 'Register New Member'})


def member_update(request, pk):
    """Update Member Profile (Update)."""
    member = get_object_or_404(Member, pk=pk)
    form = MemberForm(request.POST if request.method == 'POST' else None, instance=member)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, f'Profile of "{member.name}" updated successfully.')
            return redirect('members:list')
        messages.error(request, 'Update failed. Please correct the errors below.')
    return render(request, 'members/form.html', {'form': form, 'title': f'Update Member: {member.name}'})


def member_history(request, pk):
    """View Member History (Retrieve)."""
    member = get_object_or_404(Member, pk=pk)
    loans = member.loan_history()
    return render(request, 'members/history.html', {
        'member': member,
        'loans': loans,
        'borrowing_ready': loans is not None,
    })


@require_POST
def member_deactivate(request, pk):
    """Deactivate Account (soft delete)."""
    member = get_object_or_404(Member, pk=pk)
    if not member.is_active:
        messages.warning(request, f'"{member.name}" is already inactive.')
    elif member.has_unreturned_loans():
        messages.error(request, f'Cannot deactivate "{member.name}": there are unreturned books.')
    elif member.has_upcoming_appointments():
        messages.error(request, f'Cannot deactivate "{member.name}": there are upcoming appointments. Cancel them first.')
    else:
        member.status = Member.INACTIVE
        member.save(update_fields=['status'])
        messages.success(request, f'Account of "{member.name}" has been deactivated.')
    return redirect('members:list')


@require_POST
def member_reactivate(request, pk):
    member = get_object_or_404(Member, pk=pk)
    if member.is_active:
        messages.warning(request, f'"{member.name}" is already active.')
    else:
        member.status = Member.ACTIVE
        member.save(update_fields=['status'])
        messages.success(request, f'Account of "{member.name}" has been reactivated.')
    return redirect('members:list')


def member_delete(request, pk):
    """Delete Member: only allowed for inactive members with no loan records."""
    member = get_object_or_404(Member, pk=pk)
    if member.is_active:
        messages.error(request, 'Only inactive members can be deleted. Deactivate the account first.')
        return redirect('members:list')
    if member.has_any_loans():
        messages.error(request, f'Cannot delete "{member.name}": the member has borrowing records.')
        return redirect('members:list')
    if member.has_appointments():
        messages.error(request, f'Cannot delete "{member.name}": the member has appointment records.')
        return redirect('members:list')
    if request.method == 'POST':
        name = member.name
        member.delete()
        messages.success(request, f'Member "{name}" deleted permanently.')
        return redirect('members:list')
    return render(request, 'members/confirm_delete.html', {'member': member})


def dashboard(request):
    """Staff analytics dashboard; self-service members get their own portal."""

    if not (
        has_right(request.user, 'members.view')
        or has_right(request.user, 'accounts.manage')
    ):
        member = getattr(request.user, 'library_member', None)

        from borrowing.models import Loan

        books = Book.objects.select_related('category').annotate(
            active_loan_count=Count(
                'loans',
                filter=Q(loans__status=Loan.ACTIVE)
            )
        ).order_by('title')

        categories = Category.objects.annotate(
            book_count=Count('books')
        ).order_by('name')
        category_sections = []

        for category in categories[:4]:
            category_sections.append({
                'category': category,
                'books': books.filter(category=category)[:5],
            })
        return render(request, 'members/member_portal.html', {
            'member': member,
            'books': books,
            'categories': categories,
            'total_books': books.count(),
            'category_sections': category_sections,
        })
    


    total = Member.objects.count()
    tiers = list(MembershipType.objects.annotate(n=Count('members')))
    for t in tiers:
        t.percent = round(t.n * 100 / total) if total else 0
    categories = list(Category.objects.annotate(n=Count('books')))
    top = max([c.n for c in categories], default=0)
    for c in categories:
        c.percent = round(c.n * 100 / top) if top else 0

    context = {
        'total_members': total,
        'active_members': Member.objects.filter(status=Member.ACTIVE).count(),
        'inactive_members': Member.objects.filter(status=Member.INACTIVE).count(),
        'total_categories': len(categories),
        'total_books': Book.objects.count(),
        'uncategorised': Book.objects.filter(category__isnull=True).count(),
        'tiers': tiers,
        'categories': categories,
        'recent_members': Member.objects.select_related('membership_type').order_by('-pk')[:5],
    }

    # Student 3 – Appointment Record analytics
    if has_right(request.user, 'appointments.view'):
        today = timezone.localdate()
        now_time = timezone.localtime().time().replace(tzinfo=None)
        appointments = Appointment.objects.select_related('slot', 'member')
        booked = appointments.filter(status=Appointment.BOOKED)
        context.update({
            'can_view_appointment_dashboard': True,
            'appointment_total': appointments.count(),
            'appointment_booked': booked.count(),
            'appointment_cancelled': appointments.filter(status=Appointment.CANCELLED).count(),
            'appointment_upcoming': booked.filter(
                Q(slot__date__gt=today) |
                Q(slot__date=today, slot__start_time__gte=now_time)
            ).count(),
            'recent_appointments': appointments.order_by('-created_at')[:6],
        })
        week_labels, week_values = [], []
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            week_labels.append(day.strftime('%a'))
            week_values.append(appointments.filter(slot__date=day).count())
        context['appointment_week_labels'] = week_labels
        context['appointment_week_values'] = week_values

    # Student 3 – Library Admin & User Account analytics
    if has_right(request.user, 'accounts.manage'):
        User = get_user_model()
        user_qs = User.objects.all()
        context.update({
            'can_view_account_dashboard': True,
            'account_total': user_qs.count(),
            'account_active': user_qs.filter(is_active=True).count(),
            'account_inactive': user_qs.filter(is_active=False).count(),
        })
        role_rows = list(Role.objects.annotate(user_count=Count('profiles')).values('name', 'user_count'))
        context['role_labels'] = [row['name'] for row in role_rows]
        context['role_values'] = [row['user_count'] for row in role_rows]
        if has_right(request.user, 'audit.view'):
            context['recent_admin_activities'] = AuditLog.objects.select_related('user')[:8]

    return render(request, 'home.html', context)


def landing(request):
    """Public homepage: visitors can explore the library before signing in."""
    categories = Category.objects.annotate(book_count=Count('books')).order_by('name')
    featured_books = Book.objects.select_related('category').order_by('title')[:8]
    return render(request, 'landing.html', {
        'categories': categories,
        'featured_books': featured_books,
        'total_books': Book.objects.count(),
        'total_categories': Category.objects.count(),
    })
