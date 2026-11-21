from django.contrib import admin

from .models import Member, MembershipType


@admin.register(MembershipType)
class MembershipTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'max_books', 'loan_days')


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'membership_type', 'status')
    list_filter = ('membership_type', 'status')
