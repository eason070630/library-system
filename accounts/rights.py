"""Permission catalogue and helpers.

Other modules check access with `has_right(user, 'members.manage')`; the
AccessControlMiddleware applies these automatically to every page.
"""

RIGHT_GROUPS = [
    ('Members', [
        ('members.view', 'View members and member history'),
        ('members.manage', 'Register, edit, deactivate and delete members'),
    ]),
    ('Categories & Books', [
        ('categories.view', 'View categories and books'),
        ('categories.manage', 'Add / edit / delete categories, assign and add books'),
    ]),
    ('Appointments', [
        ('appointments.view', 'View appointments'),
        ('appointments.manage', 'Schedule and cancel appointments, manage time slots'),
    ]),
    ('Borrowing & Fines', [
        ('borrowing.view', 'View active loans, borrowing history and fine reports'),
        ('borrowing.manage', 'Checkout, renew and return books; record fine payments'),
    ]),
    ('Administration', [
        ('accounts.manage', 'Manage accounts, roles and permissions'),
        ('audit.view', 'View the system audit log'),
    ]),
]
ALL_CODES = [code for _, items in RIGHT_GROUPS for code, _ in items]

DEFAULT_ROLES = [
    ('Administrator', 'Full access to every module', ALL_CODES),
    ('Librarian', 'Manages members, books, categories, borrowing and appointments',
     ['members.view', 'members.manage', 'categories.view', 'categories.manage',
      'appointments.view', 'appointments.manage', 'borrowing.view', 'borrowing.manage', 'audit.view']),
    ('Assistant', 'Front desk: views records and handles appointments',
     ['members.view', 'categories.view', 'appointments.view', 'appointments.manage', 'borrowing.view']),
]

PROTECTED_ROLE = 'Administrator'          # cannot be renamed / deleted
REQUIRED_ADMIN_RIGHT = 'accounts.manage'  # the Administrator role must always keep this

# URL names that only need a view right; every other page of these apps needs the manage right.
VIEW_PAGES = {
    'members': {'list', 'history'},
    'categories': {'list', 'books'},
    'appointments': {'upcoming'},
    'borrowing': {'active_loans', 'history', 'fine_report', 'my_loans'},
}
PUBLIC_ACCOUNT_PAGES = {'login', 'register', 'forgot', 'reset', 'setup'}
SELF_SERVICE_PAGES = {
    'logout',
    'password_change',
    'profile',
}


def required_right(app_name, url_name):
    """Right needed to open a page, or None if any logged-in user may."""

    if app_name == 'categories' and url_name == 'member_browse':
        return None
    if app_name == 'appointments' and url_name in {
    'schedule', 'cancel', 'my_appointments'
    }:
        return None
    if app_name == 'borrowing' and url_name in {'member_borrow', 'my_loans'}:
        return None

    if app_name == 'members' and url_name == 'profile':
        return None
    
    # Allow logged-in members to access the appointment booking page.
    if app_name == 'appointments' and url_name == 'schedule':
        return None

    if app_name in VIEW_PAGES:
        return (
            f'{app_name}.view'
            if url_name in VIEW_PAGES[app_name]
            else f'{app_name}.manage'
        )

    if app_name == 'accounts':
        if url_name in SELF_SERVICE_PAGES or url_name in PUBLIC_ACCOUNT_PAGES:
            return None

        return 'audit.view' if url_name == 'audit_log' else 'accounts.manage'

    return None




def get_rights(user):
    if user is None or not user.is_authenticated:
        return set()
    if user.is_superuser:
        return set(ALL_CODES)
    cached = getattr(user, '_rights_cache', None)
    if cached is None:
        profile = getattr(user, 'profile', None)
        cached = set(profile.role.rights.values_list('code', flat=True)) if profile else set()
        user._rights_cache = cached
    return cached


def has_right(user, code):
    return code in get_rights(user)


def is_admin(user):
    return user.is_active and has_right(user, REQUIRED_ADMIN_RIGHT)
