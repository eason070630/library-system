import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from library_system.formstyle import BootstrapFormMixin

from .models import AccessRight, Role
from members.models import Member, MembershipType
from .rights import PROTECTED_ROLE, REQUIRED_ADMIN_RIGHT

User = get_user_model()
USERNAME_RE = re.compile(r'^[A-Za-z][A-Za-z0-9._]{3,29}$')
PERSON_RE = re.compile(r"^[A-Za-z][A-Za-z\s'\-\.@/]*$")
ROLE_RE = re.compile(r'^[A-Za-z][A-Za-z0-9 \-]*$')


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    pass


def _check_username(value, exclude_pk=None):
    value = value.strip()
    if not USERNAME_RE.match(value):
        raise forms.ValidationError(
            'Username must be 4-30 characters, start with a letter and use only letters, digits, "." or "_".')
    qs = User.objects.filter(username__iexact=value)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if qs.exists():
        raise forms.ValidationError('This username is already taken.')
    return value


def _check_email(value, exclude_pk=None):
    value = value.strip().lower()
    qs = User.objects.filter(email__iexact=value)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if qs.exists():
        raise forms.ValidationError('This email is already used by another account.')
    return value


def _check_person(value):
    value = ' '.join(value.split())
    if len(value) < 2 or not PERSON_RE.match(value):
        raise forms.ValidationError('Full name may only contain letters and spaces (at least 2 characters).')
    return value



class PublicRegistrationForm(BootstrapFormMixin, forms.Form):
    """Self-service library member registration with a login password."""
    username = forms.CharField(max_length=30)
    full_name = forms.CharField(max_length=100, label='Full name')
    email = forms.EmailField()
    phone = forms.CharField(max_length=15)
    address = forms.CharField(max_length=255, required=False,
                              widget=forms.Textarea(attrs={'rows': 2}))
    membership_type = forms.ModelChoiceField(
        queryset=MembershipType.objects.all(), empty_label='-- Select a membership tier --',
        label='Membership tier')
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm password', widget=forms.PasswordInput)

    def clean_username(self):
        return _check_username(self.cleaned_data['username'])

    def clean_email(self):
        email = _check_email(self.cleaned_data['email'])
        if Member.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('This email is already registered as a library member.')
        return email

    def clean_full_name(self):
        return _check_person(self.cleaned_data['full_name'])

    def clean_phone(self):
        import re
        phone = re.sub(r'[\s-]', '', self.cleaned_data['phone'])
        if not re.fullmatch(r'(?:\+?60|0)1\d{8,9}', phone):
            raise forms.ValidationError('Enter a valid Malaysian mobile number, e.g. 0123456789 or +60123456789.')
        return phone

    def clean(self):
        data = super().clean()
        p1, p2 = data.get('password1'), data.get('password2')
        if p1 and p2:
            if p1 != p2:
                self.add_error('password2', 'The two passwords do not match.')
            else:
                try:
                    validate_password(p1, User(username=data.get('username', ''), email=data.get('email', '')))
                except ValidationError as exc:
                    self.add_error('password1', exc)
        return data


class AccountEditForm(BootstrapFormMixin, forms.Form):
    full_name = forms.CharField(max_length=100)
    email = forms.EmailField()
    role = forms.ModelChoiceField(queryset=Role.objects.all(), empty_label='-- Select a role --',
                                  error_messages={'required': 'Please assign a role.',
                                                  'invalid_choice': 'Selected role does not exist.'})

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_email(self):
        return _check_email(self.cleaned_data['email'], exclude_pk=self.user.pk)

    def clean_full_name(self):
        return _check_person(self.cleaned_data['full_name'])


class SetupForm(BootstrapFormMixin, forms.Form):
    """First-run form that creates the very first administrator."""
    username = forms.CharField(max_length=30)
    full_name = forms.CharField(max_length=100)
    email = forms.EmailField()
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm password', widget=forms.PasswordInput)

    def clean_username(self):
        return _check_username(self.cleaned_data['username'])

    def clean_email(self):
        return _check_email(self.cleaned_data['email'])

    def clean_full_name(self):
        return _check_person(self.cleaned_data['full_name'])

    def clean(self):
        data = super().clean()
        p1, p2 = data.get('password1'), data.get('password2')
        if p1 and p2:
            if p1 != p2:
                self.add_error('password2', 'The two passwords do not match.')
            else:
                try:
                    validate_password(p1, User(username=data.get('username', ''), email=data.get('email', '')))
                except ValidationError as e:
                    self.add_error('password1', e)
        return data


class ForgotForm(BootstrapFormMixin, forms.Form):
    identifier = forms.CharField(label='Username or email', max_length=150,
                                 error_messages={'required': 'Please enter your username or email.'})


class NewPasswordForm(BootstrapFormMixin, forms.Form):
    new_password1 = forms.CharField(label='New password', widget=forms.PasswordInput)
    new_password2 = forms.CharField(label='Confirm new password', widget=forms.PasswordInput)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        p1, p2 = data.get('new_password1'), data.get('new_password2')
        if p1 and p2:
            if p1 != p2:
                self.add_error('new_password2', 'The two passwords do not match.')
            else:
                try:
                    validate_password(p1, self.user)
                except ValidationError as e:
                    self.add_error('new_password1', e)
        return data


class ChangePasswordForm(NewPasswordForm):
    old_password = forms.CharField(label='Current password', widget=forms.PasswordInput)
    field_order = ['old_password', 'new_password1', 'new_password2']

    def clean_old_password(self):
        if not self.user.check_password(self.cleaned_data['old_password']):
            raise forms.ValidationError('Your current password is incorrect.')
        return self.cleaned_data['old_password']

    def clean(self):
        data = super().clean()
        if data.get('old_password') and data.get('new_password1') == data.get('old_password'):
            self.add_error('new_password1', 'The new password must be different from the current one.')
        return data


class RoleForm(BootstrapFormMixin, forms.ModelForm):
    rights = forms.ModelMultipleChoiceField(queryset=AccessRight.objects.all(), required=False)

    class Meta:
        model = Role
        fields = ['name', 'description', 'rights']

    def clean_name(self):
        name = ' '.join(self.cleaned_data['name'].split())
        if len(name) < 3 or not ROLE_RE.match(name):
            raise forms.ValidationError('Role name must be at least 3 characters (letters, digits, spaces, "-").')
        qs = Role.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
            if self.instance.name == PROTECTED_ROLE and name != PROTECTED_ROLE:
                raise forms.ValidationError(f'The "{PROTECTED_ROLE}" role cannot be renamed.')
        if qs.exists():
            raise forms.ValidationError('A role with this name already exists.')
        return name

    def clean_rights(self):
        rights = self.cleaned_data['rights']
        if self.instance.pk and self.instance.name == PROTECTED_ROLE:
            if not any(r.code == REQUIRED_ADMIN_RIGHT for r in rights):
                raise forms.ValidationError(
                    f'The {PROTECTED_ROLE} role must keep "{REQUIRED_ADMIN_RIGHT}", otherwise nobody could manage accounts.')
        return rights
