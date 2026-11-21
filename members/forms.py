
import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from library_system.formstyle import BootstrapFormMixin
from .models import Member, MembershipType

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z\s'\-\.@/]*$")
PHONE_RE = re.compile(r'^(?:\+?60|0)1\d{8,9}$')

User = get_user_model()


class MemberForm(BootstrapFormMixin, forms.ModelForm):
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput,
        help_text='Set the member login password.',
        required=False
    )

    password2 = forms.CharField(
        label='Confirm password',
        widget=forms.PasswordInput,
        required=False
    )

    class Meta:
        model = Member
        fields = [
            'name', 'email', 'phone', 'address', 'membership_type'
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3})
        }
        labels = {
            'membership_type': 'Membership tier'
        }
        error_messages = {
            'membership_type': {
                'required': 'Please choose a membership tier.',
                'invalid_choice': 'Selected membership tier does not exist.'
            }
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            self.fields.pop('password1')
            self.fields.pop('password2')
        else:
            self.fields['password1'].required = True
            self.fields['password2'].required = True

        self.fields['membership_type'].queryset = MembershipType.objects.all()

    def clean_name(self):
        name = ' '.join(self.cleaned_data['name'].split())

        if len(name) < 2:
            raise forms.ValidationError(
                'Name must be at least 2 characters.'
            )

        if not NAME_RE.match(name):
            raise forms.ValidationError(
                'Name may only contain letters and spaces.'
            )

        return name

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()

        qs = Member.objects.filter(email__iexact=email)

        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError(
                'This email is already registered to another member.'
            )

        user_qs = User.objects.filter(email__iexact=email)

        if self.instance.pk and self.instance.user_id:
            user_qs = user_qs.exclude(pk=self.instance.user_id)

        if user_qs.exists():
            raise forms.ValidationError(
                'This email is already used by another login account.'
            )

        return email

    def clean_phone(self):
        phone = re.sub(r'[\s\-]', '', self.cleaned_data['phone'])

        if not PHONE_RE.match(phone):
            raise forms.ValidationError(
                'Enter a valid Malaysian mobile number, e.g. 0123456789 or +60123456789.'
            )

        return phone

    def clean(self):
        data = super().clean()

        password = data.get('password1')
        confirmation = data.get('password2')

        if not (self.instance and self.instance.pk):
            if password and confirmation and password != confirmation:
                self.add_error(
                    'password2',
                    'The two passwords do not match.'
                )
            elif password:
                try:
                    validate_password(
                        password,
                        User(
                            email=data.get('email', ''),
                            first_name=data.get('name', '')
                        )
                    )
                except ValidationError as exc:
                    self.add_error('password1', exc)

        return data


class MemberProfileForm(BootstrapFormMixin, forms.ModelForm):

    username = forms.CharField(
        max_length=150,
        label='Username'
    )

    class Meta:
        model = Member
        fields = ['email', 'membership_type']
        labels = {
            'email': 'Email',
            'membership_type': 'Membership Type',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk and self.instance.user_id:
            self.fields['username'].initial = self.instance.user.username

        self.fields['membership_type'].queryset = MembershipType.objects.all()

    def clean_username(self):
        username = self.cleaned_data['username'].strip()

        qs = User.objects.filter(username__iexact=username)

        if self.instance.user_id:
            qs = qs.exclude(pk=self.instance.user_id)

        if qs.exists():
            raise forms.ValidationError(
                'This username is already taken.'
            )

        return username

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()

        qs = Member.objects.filter(email__iexact=email)

        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError(
                'This email is already registered.'
            )

        user_qs = User.objects.filter(email__iexact=email)

        if self.instance.user_id:
            user_qs = user_qs.exclude(pk=self.instance.user_id)

        if user_qs.exists():
            raise forms.ValidationError(
                'This email is already used.'
            )

        return email
