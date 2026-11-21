from django.contrib import admin

from .models import AccessRight, AuditLog, Role, UserProfile

admin.site.register(AccessRight)
admin.site.register(Role)
admin.site.register(UserProfile)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'username', 'action', 'target')
    # the audit trail is append-only
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
