import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('members', '0003_seed_membership_types')]

    operations = [
        migrations.AlterField(
            model_name='member',
            name='membership_type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='members', to='members.membershiptype'),
        ),
    ]
