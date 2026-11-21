from urllib.parse import quote

from django.shortcuts import redirect, render
from django.urls import reverse

from . import audit
from .rights import PUBLIC_ACCOUNT_PAGES, has_right, required_right


class AccessControlMiddleware:
    """1) remembers the current request for audit logging;
    2) forces login; 3) forces a password change after an admin reset;
    4) enforces role permissions on every page."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = audit.set_request(request)
        try:
            return self.get_response(request)
        finally:
            audit.reset_request(token)

    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        if match is None or match.app_name == 'admin':   # Django's own admin has its own login
            return None
        app, name = match.app_name, match.url_name
        if name == 'home':  # public landing page
            return None
        if app == 'accounts' and name in PUBLIC_ACCOUNT_PAGES:
            return None
        if not request.user.is_authenticated:
            return redirect(f"{reverse('accounts:login')}?next={quote(request.get_full_path())}")
        profile = getattr(request.user, 'profile', None)
        if profile and profile.must_change_password and not (
                app == 'accounts' and name in {'password_change', 'logout'}):
            return redirect('accounts:password_change')
        needed = required_right(app, name)
        if needed and not has_right(request.user, needed):
            return render(request, '403.html', {'needed': needed}, status=403)
        return None
