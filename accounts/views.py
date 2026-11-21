import csv
import secrets
import string

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, update_session_auth_hash
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import LoginView
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_POST

from .audit import log_action
from .forms import (AccountEditForm, ChangePasswordForm, ForgotForm,
                    LoginForm, NewPasswordForm, RoleForm, SetupForm, PublicRegistrationForm)
from .models import AccessRight, AuditLog, Role, UserProfile
from .rights import PROTECTED_ROLE, is_admin

User = get_user_model()


def temp_password(length=10):
    alphabet = string.ascii_letters + string.digits
    while True:
        pw = ''.join(secrets.choice(alphabet) for _ in range(length))
        if any(c.isalpha() for c in pw) and any(c.isdigit() for c in pw):
            return pw


def other_admins(exclude_user):
    """Active accounts (other than exclude_user) that can still manage accounts."""
    return [u for u in User.objects.filter(is_active=True).exclude(pk=exclude_user.pk)
            .select_related('profile__role') if is_admin(u)]


# ------------------------------------------------------------ login / first run
class AppLoginView(LoginView):
    authentication_form = LoginForm
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['no_admin'] = not User.objects.filter(
            Q(is_superuser=True) | Q(profile__role__name=PROTECTED_ROLE)).exists()
        return ctx


def register(request):
    """Public self-service registration: create login credentials and a library member."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = PublicRegistrationForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        with transaction.atomic():
            user = User.objects.create_user(
                username=d['username'], email=d['email'], password=d['password1'],
                first_name=d['full_name'])
            from members.models import Member
            Member.objects.create(
                user=user, name=d['full_name'], email=d['email'], phone=d['phone'],
                address=d['address'], membership_type=d['membership_type'])
        log_action('member_register', f'User: {user.username}',
                   'Self-service library member registration', request=request, user=user)
        messages.success(request, 'Registration successful. Please log in with your new username and password.')
        return redirect('accounts:login')
    return render(request, 'accounts/register.html', {'form': form})


def setup(request):
    """First run only: create the first administrator."""
    if User.objects.filter(is_superuser=True).exists() or User.objects.filter(
            profile__role__name=PROTECTED_ROLE).exists():
        messages.info(request, 'Setup is already done. Please log in.')
        return redirect('accounts:login')
    form = SetupForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST':
        if form.is_valid():
            d = form.cleaned_data
            admin_role = Role.objects.get(name=PROTECTED_ROLE)
            with transaction.atomic():
                user = User.objects.create_superuser(d['username'], d['email'], d['password1'],
                                                     first_name=d['full_name'])
                UserProfile.objects.create(user=user, role=admin_role)
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, f'Welcome, {user.first_name}! The first administrator account was created.')
            return redirect('dashboard')
        messages.error(request, 'Setup failed. Please correct the errors below.')
    return render(request, 'accounts/setup.html', {'form': form})


# ------------------------------------------------ 1. Create Account & Assign Roles
def account_list(request):
    q = request.GET.get('q', '').strip()
    role = request.GET.get('role', '')
    status = request.GET.get('status', '')
    users = User.objects.select_related('profile__role').order_by('username')
    if q:
        users = users.filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(email__icontains=q))
    if role.isdigit():
        users = users.filter(profile__role_id=int(role))
    if status == 'active':
        users = users.filter(is_active=True)
    elif status == 'inactive':
        users = users.filter(is_active=False)
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="user_accounts.csv"'
        response.write('\\ufeff')
        writer = csv.writer(response)
        writer.writerow(['Username', 'Full name', 'Email', 'Role', 'Status', 'Last login'])
        for account in users:
            profile = getattr(account, 'profile', None)
            writer.writerow([account.username, account.first_name, account.email,
                             profile.role.name if profile else 'No role',
                             'Active' if account.is_active else 'Inactive',
                             account.last_login.strftime('%Y-%m-%d %H:%M:%S') if account.last_login else 'Never'])
        return response
    return render(request, 'accounts/account_list.html', {
        'users': users, 'q': q, 'role': role, 'status': status, 'roles': Role.objects.all()})


def account_edit(request, pk):
    target = get_object_or_404(User.objects.select_related('profile__role'), pk=pk)
    profile = getattr(target, 'profile', None)
    initial = {'full_name': target.first_name, 'email': target.email, 'role': profile.role if profile else None}
    form = AccountEditForm(request.POST if request.method == 'POST' else None, initial=initial, user=target)
    if request.method == 'POST':
        if form.is_valid():
            d = form.cleaned_data
            old_role = profile.role if profile else None
            new_role = d['role']
            if (old_role != new_role and is_admin(target)
                    and 'accounts.manage' not in set(new_role.rights.values_list('code', flat=True))
                    and not target.is_superuser and not other_admins(target)):
                form.add_error('role', 'This is the last administrator. Assign another administrator first.')
            else:
                target.first_name, target.email = d['full_name'], d['email']
                target.save()
                if profile:
                    profile.role = new_role
                    profile.save()
                else:
                    UserProfile.objects.create(user=target, role=new_role)
                if old_role != new_role:
                    log_action('assign_role', f'User: {target.username}',
                               f'Role changed {old_role} -> {new_role}')
                messages.success(request, f'Account "{target.username}" updated successfully.')
                return redirect('accounts:account_list')
        messages.error(request, 'Update failed. Please correct the errors below.')
    return render(request, 'accounts/account_form.html', {
        'form': form, 'title': f'Edit Account: {target.username}', 'target': target})


@require_POST
def account_toggle(request, pk):
    target = get_object_or_404(User, pk=pk)
    if target.pk == request.user.pk:
        messages.error(request, 'You cannot deactivate your own account.')
    elif target.is_active:
        if is_admin(target) and not other_admins(target):
            messages.error(request, 'This is the last active administrator and cannot be deactivated.')
        else:
            target.is_active = False
            target.save()
            messages.success(request, f'Account "{target.username}" deactivated.')
    else:
        target.is_active = True
        target.save()
        messages.success(request, f'Account "{target.username}" reactivated.')
    return redirect('accounts:account_list')


def account_delete(request, pk):
    """Permanently delete an account after a confirmation page."""
    target = get_object_or_404(User.objects.select_related('profile__role'), pk=pk)
    if target.pk == request.user.pk:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('accounts:account_list')
    if is_admin(target) and not other_admins(target):
        messages.error(request, 'The last active administrator cannot be deleted.')
        return redirect('accounts:account_list')
    if request.method == 'POST':
        username = target.username
        log_action('account_delete', f'User: {username}', 'Account permanently deleted',
                   request=request, user=request.user)
        target.delete()
        messages.success(request, f'Account "{username}" permanently deleted.')
        return redirect('accounts:account_list')
    return render(request, 'accounts/account_confirm_delete.html', {'target': target})


# --------------------------------------------- 2. Password Reset & Recovery
@require_POST
def account_reset_password(request, pk):
    """Administrator resets someone's password: a temporary one is generated."""
    target = get_object_or_404(User, pk=pk)
    pw = temp_password()
    target.set_password(pw)
    target.save()
    profile = getattr(target, 'profile', None)
    if profile:
        profile.must_change_password = True
        profile.save()
    log_action('password_reset', f'User: {target.username}', 'Reset by administrator (temporary password issued)')
    messages.success(request, f'Password of "{target.username}" reset. Temporary password: {pw} '
                              '(shown only once; the user must change it at next login).')
    return redirect('accounts:account_list')


def forgot(request):
    """Self-service recovery: a time-limited reset link is e-mailed (printed in the terminal)."""
    form = ForgotForm(request.POST if request.method == 'POST' else None)
    done, demo_link = False, None
    if request.method == 'POST' and form.is_valid():
        ident = form.cleaned_data['identifier'].strip()
        user = User.objects.filter(is_active=True).filter(Q(username__iexact=ident) | Q(email__iexact=ident)).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            link = request.build_absolute_uri(reverse('accounts:reset', args=[uid, default_token_generator.make_token(user)]))
            body = (f'Hello {user.first_name or user.username},\n\nUse this link to reset your library account '
                    f'password (valid for 1 hour):\n{link}\n\nIf you did not ask for this, ignore this e-mail.')
            try:
                if user.email:
                    send_mail('Library System password reset', body, 'library@localhost', [user.email])
            except Exception:
                pass  # no mail server configured: the link is still available in demo mode below
            log_action('password_reset_request', f'User: {user.username}', request=request, user=user)
            if settings.DEBUG:
                demo_link = link
        done = True
    return render(request, 'accounts/forgot.html', {'form': form, 'done': done, 'demo_link': demo_link})


def _user_from_token(uidb64, token):
    try:
        user = User.objects.get(pk=urlsafe_base64_decode(uidb64).decode(), is_active=True)
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        return None
    return user if default_token_generator.check_token(user, token) else None


def reset(request, uidb64, token):
    user = _user_from_token(uidb64, token)
    if user is None:
        return render(request, 'accounts/reset_invalid.html', status=400)
    form = NewPasswordForm(user, request.POST if request.method == 'POST' else None)
    if request.method == 'POST':
        if form.is_valid():
            user.set_password(form.cleaned_data['new_password1'])
            user.save()
            profile = getattr(user, 'profile', None)
            if profile and profile.must_change_password:
                profile.must_change_password = False
                profile.save()
            log_action('password_reset', f'User: {user.username}', 'Reset via recovery link', request=request, user=user)
            messages.success(request, 'Your password has been reset. Please log in with the new password.')
            return redirect('accounts:login')
        messages.error(request, 'Could not reset the password. Please correct the errors below.')
    return render(request, 'accounts/reset.html', {'form': form})


def password_change(request):
    user = request.user
    profile = getattr(user, 'profile', None)
    forced = bool(profile and profile.must_change_password)
    form = ChangePasswordForm(user, request.POST if request.method == 'POST' else None)
    if request.method == 'POST':
        if form.is_valid():
            user.set_password(form.cleaned_data['new_password1'])
            user.save()
            if profile and profile.must_change_password:
                profile.must_change_password = False
                profile.save()
            update_session_auth_hash(request, user)
            log_action('password_change', f'User: {user.username}', request=request)
            messages.success(request, 'Your password has been changed.')
            return redirect('dashboard')
        messages.error(request, 'Could not change the password. Please correct the errors below.')
    return render(request, 'accounts/password_change.html', {'form': form, 'forced': forced})


# ------------------------------------------------------ 3. Manage Permissions
def _right_groups():
    groups = {}
    for r in AccessRight.objects.all():
        groups.setdefault(r.module, []).append(r)
    return list(groups.items())


def role_list(request):
    roles = Role.objects.annotate(user_count=Count('profiles', distinct=True), right_count=Count('rights', distinct=True))
    return render(request, 'accounts/role_list.html', {'roles': roles, 'protected': PROTECTED_ROLE})


def _role_form_view(request, role, title):
    form = RoleForm(request.POST if request.method == 'POST' else None, instance=role)
    selected = ({int(v) for v in request.POST.getlist('rights') if v.isdigit()} if request.method == 'POST'
                else set(role.rights.values_list('pk', flat=True)) if role else set())
    if request.method == 'POST':
        if form.is_valid():
            before = set(role.rights.values_list('code', flat=True)) if role else set()
            saved = form.save()
            after = set(saved.rights.values_list('code', flat=True))
            added, removed = sorted(after - before), sorted(before - after)
            detail = '; '.join(filter(None, [f'granted: {", ".join(added)}' if added else '',
                                              f'revoked: {", ".join(removed)}' if removed else '']))
            if detail or not role:
                log_action('permissions', f'Role: {saved.name}', detail or 'Role created without permissions')
            messages.success(request, f'Role "{saved.name}" saved successfully.')
            return redirect('accounts:role_list')
        messages.error(request, 'Could not save the role. Please correct the errors below.')
    return render(request, 'accounts/role_form.html', {
        'form': form, 'title': title, 'role': role, 'groups': _right_groups(), 'selected': selected})


def role_create(request):
    return _role_form_view(request, None, 'Create Role')


def role_edit(request, pk):
    role = get_object_or_404(Role, pk=pk)
    return _role_form_view(request, role, f'Manage Permissions: {role.name}')


def role_delete(request, pk):
    role = get_object_or_404(Role, pk=pk)
    if role.name == PROTECTED_ROLE:
        messages.error(request, f'The "{PROTECTED_ROLE}" role cannot be deleted.')
        return redirect('accounts:role_list')
    count = role.profiles.count()
    if count:
        messages.error(request, f'Cannot delete "{role.name}": {count} account(s) still use it. Reassign them first.')
        return redirect('accounts:role_list')
    if request.method == 'POST':
        name = role.name
        role.delete()
        messages.success(request, f'Role "{name}" deleted successfully.')
        return redirect('accounts:role_list')
    return render(request, 'accounts/role_confirm_delete.html', {'role': role})


# ------------------------------------------------------ 4. View System Audit Logs
def audit_log(request):
    q = request.GET.get('q', '').strip()
    action = request.GET.get('action', '')
    user = request.GET.get('user', '').strip()
    d_from, d_to = request.GET.get('from', ''), request.GET.get('to', '')
    logs = AuditLog.objects.all()
    if q:
        logs = logs.filter(Q(target__icontains=q) | Q(detail__icontains=q))
    if action:
        logs = logs.filter(action=action)
    if user:
        logs = logs.filter(username__icontains=user)
    from datetime import date
    for val, lookup in ((d_from, 'timestamp__date__gte'), (d_to, 'timestamp__date__lte')):
        if val:
            try:
                logs = logs.filter(**{lookup: date.fromisoformat(val)})
            except ValueError:
                messages.warning(request, f'Ignored invalid date "{val}".')
    if request.GET.get('export') == 'csv':
        resp = HttpResponse(content_type='text/csv')
        resp['Content-Disposition'] = 'attachment; filename="audit_log.csv"'
        w = csv.writer(resp)
        w.writerow(['Time', 'User', 'Action', 'Target', 'Detail', 'IP'])
        for l in logs[:5000]:
            w.writerow([l.timestamp.strftime('%Y-%m-%d %H:%M:%S'), l.username, l.action, l.target, l.detail, l.ip or ''])
        return resp
    page = Paginator(logs, 25).get_page(request.GET.get('page'))
    qs = request.GET.copy()
    qs.pop('page', None)
    return render(request, 'accounts/audit_log.html', {
        'page': page, 'q': q, 'action': action, 'user_q': user, 'd_from': d_from, 'd_to': d_to,
        'actions': AuditLog.objects.order_by().values_list('action', flat=True).distinct(),
        'qs': qs.urlencode()})
