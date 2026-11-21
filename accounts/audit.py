import contextvars
import logging

from django.db import transaction

logger = logging.getLogger(__name__)

_current_request = contextvars.ContextVar('current_request', default=None)
_suppressed = contextvars.ContextVar('audit_suppressed', default=False)


class suppressed:
    """`with suppressed():` skips audit logging (used when loading demo data)."""
    def __enter__(self):
        self._t = _suppressed.set(True)

    def __exit__(self, *exc):
        _suppressed.reset(self._t)


def set_request(request):
    return _current_request.set(request)


def reset_request(token):
    _current_request.reset(token)


def get_request():
    return _current_request.get()


def client_ip(request):
    if request is None:
        return None
    fwd = request.META.get('HTTP_X_FORWARDED_FOR')
    return (fwd.split(',')[0].strip() if fwd else request.META.get('REMOTE_ADDR')) or None


def log_action(action, target='', detail='', request=None, user=None, username=None):
    """Write one audit-log row. The acting user is taken from the current request."""
    from .models import AuditLog
    if _suppressed.get():
        return
    request = request or get_request()
    actor = user
    if actor is None and request is not None:
        u = getattr(request, 'user', None)
        if u is not None and u.is_authenticated:
            actor = u
    name = username or (actor.get_username() if actor else 'system')
    try:
        with transaction.atomic():   # savepoint: a logging failure must never break the real action
            AuditLog.objects.create(
                user=actor, username=name[:150], action=action, target=target[:200],
                detail=detail, ip=client_ip(request))
    except Exception:
        logger.exception('Could not write audit log entry (%s %s)', action, target)
