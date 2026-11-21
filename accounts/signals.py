"""Automatic audit trail: every create / update / delete of the tracked models,
plus logins, logouts and failed logins, is recorded in AuditLog."""
import datetime

from django.apps import apps
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_delete, post_save, pre_save
from django.utils import timezone

from .audit import log_action

TRACKED = [
    'members.Member', 'members.MembershipType',
    'categories.Category', 'categories.Book',
    'appointments.TimeSlot', 'appointments.Appointment',
    'accounts.Role', 'auth.User',
]
SKIP_FIELDS = {'password', 'last_login'}  # never log password hashes / login noise


def _label(obj):
    return f'{obj._meta.verbose_name.title()}: {obj}'


def _fmt(value):
    """Readable value for the audit detail column."""
    if value is None or value == '':
        return '(empty)'
    if isinstance(value, datetime.datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.strftime('%Y-%m-%d %H:%M')
    if isinstance(value, (datetime.date, datetime.time)):
        return str(value)[:16]
    return repr(value) if isinstance(value, str) else str(value)


def _changes(old, new):
    out = []
    for f in new._meta.concrete_fields:
        if f.name in SKIP_FIELDS or f.primary_key:
            continue
        a, b = f.value_from_object(old), f.value_from_object(new)
        if a != b:
            out.append(f'{f.verbose_name}: {_fmt(a)} -> {_fmt(b)}')
    return '; '.join(out)


def _pre_save(sender, instance, raw=False, **kwargs):
    instance._audit_changes = None
    if raw or not instance.pk:
        return
    old = sender._default_manager.filter(pk=instance.pk).first()
    if old is not None:
        instance._audit_changes = _changes(old, instance)


def _post_save(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    if created:
        log_action('create', _label(instance))
        return
    changes = getattr(instance, '_audit_changes', None)
    if changes == '':  # nothing meaningful changed (e.g. only last_login)
        return
    log_action('update', _label(instance), changes or '')


def _post_delete(sender, instance, **kwargs):
    log_action('delete', _label(instance))


def _logged_in(sender, request, user, **kwargs):
    log_action('login', f'User: {user.get_username()}', request=request, user=user)


def _logged_out(sender, request, user, **kwargs):
    if user is not None:
        log_action('logout', f'User: {user.get_username()}', request=request, user=user)


def _login_failed(sender, credentials, request=None, **kwargs):
    name = credentials.get('username') or 'unknown'
    log_action('login_failed', f'User: {name}', 'Invalid username or password',
               request=request, username=name)


def connect():
    for label in TRACKED:
        model = apps.get_model(label)
        pre_save.connect(_pre_save, sender=model, dispatch_uid=f'audit_pre_{label}')
        post_save.connect(_post_save, sender=model, dispatch_uid=f'audit_post_{label}')
        post_delete.connect(_post_delete, sender=model, dispatch_uid=f'audit_del_{label}')
    user_logged_in.connect(_logged_in, dispatch_uid='audit_login')
    user_logged_out.connect(_logged_out, dispatch_uid='audit_logout')
    user_login_failed.connect(_login_failed, dispatch_uid='audit_login_failed')
