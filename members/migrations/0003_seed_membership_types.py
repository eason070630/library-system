from django.db import migrations

TIERS = [
    # name, level, max_books, loan_days, description, badge colour
    ('Basic', 1, 3, 14, 'Entry level: up to 3 books for 14 days', 'secondary'),
    ('Silver', 2, 6, 21, 'Up to 6 books for 21 days', 'info'),
    ('Gold', 3, 10, 30, 'Up to 10 books for 30 days', 'warning'),
]


def seed(apps, schema_editor):
    MembershipType = apps.get_model('members', 'MembershipType')
    Member = apps.get_model('members', 'Member')
    for name, level, max_books, loan_days, desc, color in TIERS:
        MembershipType.objects.get_or_create(
            name=name,
            defaults=dict(level=level, max_books=max_books, loan_days=loan_days,
                          description=desc, badge_color=color))
    basic = MembershipType.objects.get(name='Basic')
    Member.objects.filter(membership_type__isnull=True).update(membership_type=basic)


class Migration(migrations.Migration):

    dependencies = [('members', '0002_membershiptype_member_membership_type')]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
