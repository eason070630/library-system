from django.db import migrations

# Frozen copy of the catalogue (migrations must not import app code that may change later).
RIGHTS = [
    ('Members', 'members.view', 'View members and member history'),
    ('Members', 'members.manage', 'Register, edit, deactivate and delete members'),
    ('Categories & Books', 'categories.view', 'View categories and books'),
    ('Categories & Books', 'categories.manage', 'Add / edit / delete categories, assign and add books'),
    ('Appointments', 'appointments.view', 'View appointments'),
    ('Appointments', 'appointments.manage', 'Schedule and cancel appointments, manage time slots'),
    ('Administration', 'accounts.manage', 'Manage accounts, roles and permissions'),
    ('Administration', 'audit.view', 'View the system audit log'),
]
ROLES = [
    ('Administrator', 'Full access to every module', [r[1] for r in RIGHTS]),
    ('Librarian', 'Manages members, books, categories and appointments',
     ['members.view', 'members.manage', 'categories.view', 'categories.manage',
      'appointments.view', 'appointments.manage', 'audit.view']),
    ('Assistant', 'Front desk: views records and handles appointments',
     ['members.view', 'categories.view', 'appointments.view', 'appointments.manage']),
]


def seed(apps, schema_editor):
    AccessRight = apps.get_model('accounts', 'AccessRight')
    Role = apps.get_model('accounts', 'Role')
    by_code = {}
    for module, code, label in RIGHTS:
        by_code[code], _ = AccessRight.objects.get_or_create(
            code=code, defaults={'label': label, 'module': module})
    for name, desc, codes in ROLES:
        role, _ = Role.objects.get_or_create(name=name, defaults={'description': desc})
        role.rights.set([by_code[c] for c in codes])


class Migration(migrations.Migration):
    dependencies = [('accounts', '0001_initial')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
