from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('borrowing', '0001_initial'),
        ('members', '0005_member_user'),
        ('categories', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BorrowRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=10)),
                ('requested_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('review_note', models.CharField(blank=True, max_length=255)),
                ('book', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='borrow_requests', to='categories.book')),
                ('loan', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='borrow_request', to='borrowing.loan')),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='borrow_requests', to='members.member')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_borrow_requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-requested_at', '-pk']},
        ),
    ]
