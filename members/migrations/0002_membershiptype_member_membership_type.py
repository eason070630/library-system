import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('members', '0001_initial')]

    operations = [
        migrations.CreateModel(
            name='MembershipType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=30, unique=True)),
                ('level', models.PositiveSmallIntegerField(help_text='1 = lowest tier', unique=True)),
                ('max_books', models.PositiveSmallIntegerField(help_text='Max books borrowed at the same time')),
                ('loan_days', models.PositiveSmallIntegerField(help_text='Days allowed per loan')),
                ('description', models.CharField(blank=True, max_length=150)),
                ('badge_color', models.CharField(default='secondary', help_text='Bootstrap colour name, e.g. secondary, primary, warning', max_length=20)),
            ],
            options={'ordering': ['level']},
        ),
        migrations.AddField(
            model_name='member',
            name='membership_type',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='members', to='members.membershiptype'),
        ),
    ]
