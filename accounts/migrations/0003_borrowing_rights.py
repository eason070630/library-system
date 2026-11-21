from django.db import migrations

RIGHTS = [
    ('borrowing.view', 'View active loans, borrowing history and fine reports'),
    ('borrowing.manage', 'Checkout, renew and return books; record fine payments'),
]


def add_rights(apps, schema_editor):
    AccessRight = apps.get_model('accounts', 'AccessRight')
    Role = apps.get_model('accounts', 'Role')
    for code, label in RIGHTS:
        right, _ = AccessRight.objects.get_or_create(
            code=code, defaults={'label': label, 'module': 'Borrowing & Fines'})
        # Administrator and Librarian can manage all borrowing functions.
        for role_name in ('Administrator', 'Librarian'):
            role = Role.objects.filter(name=role_name).first()
            if role:
                role.rights.add(right)
        # Assistant can view active loans/history but cannot issue or return books.
        if code == 'borrowing.view':
            role = Role.objects.filter(name='Assistant').first()
            if role:
                role.rights.add(right)


def remove_rights(apps, schema_editor):
    AccessRight = apps.get_model('accounts', 'AccessRight')
    AccessRight.objects.filter(code__in=[r[0] for r in RIGHTS]).delete()


class Migration(migrations.Migration):
    dependencies = [('accounts', '0002_seed_rights_and_roles')]
    operations = [migrations.RunPython(add_rights, remove_rights)]
