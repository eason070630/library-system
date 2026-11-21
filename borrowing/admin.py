from django.contrib import admin
from .models import Loan, FinePayment


class FinePaymentInline(admin.TabularInline):
    model = FinePayment
    extra = 0


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ('id', 'member', 'book', 'checkout_date', 'due_date', 'return_date', 'status', 'fine_amount')
    list_filter = ('status', 'checkout_date', 'return_date')
    search_fields = ('member__name', 'member__email', 'book__title', 'book__isbn')
    inlines = [FinePaymentInline]


@admin.register(FinePayment)
class FinePaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'loan', 'amount', 'method', 'paid_at', 'received_by')
    list_filter = ('method', 'paid_at')
    search_fields = ('loan__member__name', 'loan__book__title', 'reference')
