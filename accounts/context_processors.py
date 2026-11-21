from .rights import get_rights


def access(request):
    user = getattr(request, 'user', None)
    role = None
    if user is not None and user.is_authenticated:
        role = 'Superuser' if user.is_superuser else getattr(getattr(user, 'profile', None), 'role', None)
    return {'user_rights': get_rights(user), 'current_role': role}
