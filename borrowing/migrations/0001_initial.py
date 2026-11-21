import datetime
import decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('members', '0005_member_user'),
        ('categories', '0001_initial'),
    ]
    operations = [
        migrations.CreateModel(
            name='Loan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('checkout_date', models.DateField(default=django.utils.timezone.localdate)),
                ('due_date', models.DateField()),
                ('return_date', models.DateField(blank=True, null=True)),
                ('status', models.CharField(choices=[('active', 'Active'), ('returned', 'Returned')], default='active', max_length=10)),
                ('renewal_count', models.PositiveSmallIntegerField(default=0)),
                ('fine_amount', models.DecimalField(decimal_places=2, default=decimal.Decimal('0.00'), max_digits=8)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('book', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='loans', to='categories.book')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_loans', to=settings.AUTH_USER_MODEL)),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='loans', to='members.member')),
                ('returned_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='returned_loans', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-checkout_date', '-pk']},
        ),
        migrations.CreateModel(
            name='FinePayment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=8)),
                ('method', models.CharField(choices=[('cash', 'Cash'), ('card', 'Card'), ('online', 'Online transfer')], default='cash', max_length=10)),
                ('reference', models.CharField(blank=True, max_length=80)),
                ('paid_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('note', models.CharField(blank=True, max_length=200)),
                ('loan', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='payments', to='borrowing.loan')),
                ('received_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='fine_payments_received', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-paid_at', '-pk']},
        ),
        migrations.AddConstraint(
            model_name='loan',
            constraint=models.UniqueConstraint(condition=models.Q(('status', 'active')), fields=('book',), name='one_active_loan_per_book'),
        ),
    ]
