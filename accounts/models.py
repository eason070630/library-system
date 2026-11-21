from django.conf import settings
from django.db import models


class AccessRight(models.Model):
    """One permission that can be granted to a role, e.g. 'members.manage'."""
    code = models.CharField(max_length=40, unique=True)
    label = models.CharField(max_length=120)
    module = models.CharField(max_length=40)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.code


class Role(models.Model):
    name = models.CharField(max_length=30, unique=True)
    description = models.CharField(max_length=150, blank=True)
    rights = models.ManyToManyField(AccessRight, blank=True, related_name='roles')

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    """Extra data for a Django auth user: which role they hold."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name='profiles')
    must_change_password = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.get_username()} ({self.role})'


class AuditLog(models.Model):
    """Append-only record of who did what and when."""
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                             on_delete=models.SET_NULL, related_name='+')
    username = models.CharField(max_length=150)  # kept even if the user is later removed
    action = models.CharField(max_length=30, db_index=True)
    target = models.CharField(max_length=200, blank=True)
    detail = models.TextField(blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp', '-id']

    def __str__(self):
        return f'{self.timestamp:%Y-%m-%d %H:%M} {self.username} {self.action}'
