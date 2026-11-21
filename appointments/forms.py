
from datetime import time

from django import forms
from django.utils import timezone

from categories.models import Book
from library_system.formstyle import BootstrapFormMixin
from members.models import Member

from .models import Appointment, TimeSlot, now_local


OPEN, CLOSE = time(8, 0), time(20, 0)


# ==========================================
# TIME SLOT FORM
# Used by Admin / Librarian to add and edit slots
# ==========================================

class SlotForm(BootstrapFormMixin, forms.ModelForm):

    class Meta:
        model = TimeSlot
        fields = [
            'date',
            'start_time',
            'end_time',
            'capacity',
            'note',
            'is_active'
        ]

        widgets = {
            'date': forms.DateInput(
                attrs={'type': 'date'},
                format='%Y-%m-%d'
            ),
            'start_time': forms.TimeInput(
                attrs={'type': 'time'},
                format='%H:%M'
            ),
            'end_time': forms.TimeInput(
                attrs={'type': 'time'},
                format='%H:%M'
            ),
        }

    def clean(self):
        data = super().clean()

        date = data.get('date')
        start = data.get('start_time')
        end = data.get('end_time')
        cap = data.get('capacity')

        # Cannot edit a slot that has already started
        if self.instance.pk and self.instance.has_started():
            raise forms.ValidationError(
                'This slot has already started and can no longer be edited.'
            )

        # Date validation
        if date and date < timezone.localdate():
            self.add_error(
                'date',
                'The date cannot be in the past.'
            )

        # Time validation
        if start and end:

            if end <= start:
                self.add_error(
                    'end_time',
                    'End time must be after the start time.'
                )

            elif (
                (end.hour * 60 + end.minute)
                - (start.hour * 60 + start.minute)
            ) < 15:
                self.add_error(
                    'end_time',
                    'A slot must be at least 15 minutes long.'
                )

            if start < OPEN or end > CLOSE:
                self.add_error(
                    'start_time',
                    f'Slots must fall within opening hours '
                    f'({OPEN:%H:%M}-{CLOSE:%H:%M}).'
                )

        # Cannot create a slot with a start time that has passed today
        if (
            date
            and start
            and 'date' not in self.errors
            and not self.instance.pk
        ):
            if date == timezone.localdate() and start <= now_local().time():
                self.add_error(
                    'start_time',
                    'This start time has already passed today.'
                )

        # Capacity validation
        if cap is not None:

            if not 1 <= cap <= 20:
                self.add_error(
                    'capacity',
                    'Capacity must be between 1 and 20.'
                )

            elif (
                self.instance.pk
                and cap < self.instance.booked_count
            ):
                self.add_error(
                    'capacity',
                    f'{self.instance.booked_count} members have already '
                    'booked this slot; capacity cannot be lower than that.'
                )

        # Prevent overlapping active slots
        if (
            date
            and start
            and end
            and data.get('is_active')
            and not self.errors
        ):
            clash = TimeSlot.objects.filter(
                date=date,
                is_active=True,
                start_time__lt=end,
                end_time__gt=start
            )

            if self.instance.pk:
                clash = clash.exclude(pk=self.instance.pk)

            if clash.exists():
                raise forms.ValidationError(
                    f'This overlaps an existing active slot '
                    f'({clash.first()}).'
                )

        return data


# ==========================================
# SLOT CHOICE FIELD
# Used by AppointmentForm
# ==========================================

class SlotChoiceField(forms.ModelChoiceField):

    def label_from_instance(self, slot):
        left = slot.seats_left

        status = f'{left} left' if left else 'FULL'

        extra = f' · {slot.note}' if slot.note else ''

        return (
            f'{slot.date:%a %d %b %Y}  '
            f'{slot.start_time:%H:%M}-{slot.end_time:%H:%M}  '
            f'({status}){extra}'
        )


# ==========================================
# APPOINTMENT FORM
# Used by Member / Librarian to make appointments
# ==========================================

class AppointmentForm(BootstrapFormMixin, forms.Form):

    member = forms.ModelChoiceField(
        queryset=Member.objects.none(),
        empty_label='-- Select a member --',
        error_messages={
            'required': 'Please select a member.',
            'invalid_choice': (
                'Selected member does not exist or is inactive.'
            )
        }
    )

    slot = SlotChoiceField(
        queryset=TimeSlot.objects.none(),
        empty_label='-- Select a time slot --',
        error_messages={
            'required': 'Please select a time slot.',
            'invalid_choice': 'Selected time slot is not available.'
        }
    )

    purpose = forms.ChoiceField(
        choices=[
            ('', '-- Select a purpose --')
        ] + Appointment.PURPOSE_CHOICES,
        error_messages={
            'required': 'Please choose a purpose.'
        }
    )

    book = forms.ModelChoiceField(
        queryset=Book.objects.none(),
        required=False,
        empty_label='-- No book --',
        label='Book to pick up'
    )

    note = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.Textarea(attrs={'rows': 2})
    )

    def __init__(self, *args, member=None, **kwargs):
        super().__init__(*args, **kwargs)

        if member is not None:
            # Member can only select their own account
            self.fields['member'].queryset = Member.objects.filter(
                pk=member.pk,
                status=Member.ACTIVE
            )

            self.fields['member'].initial = member.pk
            self.fields['member'].widget = forms.HiddenInput()

        else:
            # Librarian can select any active member
            self.fields['member'].queryset = Member.objects.filter(
                status=Member.ACTIVE
            ).select_related('membership_type')

        self.fields['slot'].queryset = TimeSlot.objects.filter(
            is_active=True,
            date__gte=timezone.localdate()
        )

        self.fields['book'].queryset = Book.objects.all()

    def clean(self):
        data = super().clean()

        member = data.get('member')
        slot = data.get('slot')
        purpose = data.get('purpose')
        book = data.get('book')

        # Book pickup validation
        if purpose == Appointment.PICKUP and not book:
            self.add_error(
                'book',
                'Please choose the book to pick up.'
            )

        if purpose and purpose != Appointment.PICKUP and book:
            self.add_error(
                'book',
                'A book can only be chosen for a "Book pickup" appointment.'
            )

        if not (member and slot):
            return data

        # Slot must not have started
        if slot.has_started():
            self.add_error(
                'slot',
                'This time slot has already started.'
            )
            return data

        # Slot must have available seats
        if slot.seats_left <= 0:
            self.add_error(
                'slot',
                'This time slot is full. Please choose another one.'
            )
            return data

        # Check existing appointments
        mine = Appointment.objects.filter(
            member=member,
            status=Appointment.BOOKED
        )

        if mine.filter(slot=slot).exists():
            self.add_error(
                'member',
                'This member has already booked this time slot.'
            )
            return data

        if mine.filter(
            slot__date=slot.date,
            slot__start_time__lt=slot.end_time,
            slot__end_time__gt=slot.start_time
        ).exists():
            self.add_error(
                'member',
                'This member already has an appointment that overlaps this time.'
            )
            return data

        # Membership appointment limit
        limit = member.membership_type.level + 1

        upcoming = sum(
            1
            for appointment in mine.select_related('slot')
            if not appointment.slot.has_started()
        )

        if upcoming >= limit:
            self.add_error(
                'member',
                f'{member.membership_type.name} members can hold at most '
                f'{limit} upcoming appointments '
                f'(already has {upcoming}).'
            )

        return data


# ==========================================
# CANCEL FORM
# ==========================================

class CancelForm(BootstrapFormMixin, forms.Form):

    reason = forms.CharField(
        max_length=200,
        required=False,
        label='Reason (optional)',
        widget=forms.Textarea(attrs={'rows': 2}),
        error_messages={
            'max_length': 'Reason must be 200 characters or fewer.'
        }
    )
