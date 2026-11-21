from datetime import timedelta
import csv

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from members.models import Member

from .forms import AppointmentForm, CancelForm, SlotForm
from .models import Appointment, TimeSlot, now_local
from django import forms
from django.contrib.auth.decorators import login_required
def _upcoming_q(prefix='slot__'):
    now = now_local()
    return (Q(**{f'{prefix}date__gt': now.date()}) |
            Q(**{f'{prefix}date': now.date(), f'{prefix}start_time__gt': now.time()}))


# ---------------------------------------------------------------- Appointments
def upcoming(request):
    """View Upcoming Appointments (also past / cancelled tabs)."""
    show = request.GET.get('show', 'upcoming')
    member_id = request.GET.get('member', '')
    date = request.GET.get('date', '')
    qs = Appointment.objects.select_related('member', 'member__membership_type', 'slot', 'book')
    if show == 'cancelled':
        qs = qs.filter(status=Appointment.CANCELLED).order_by('-slot__date', '-slot__start_time')
    elif show == 'past':
        qs = qs.filter(status=Appointment.BOOKED).exclude(_upcoming_q()).order_by('-slot__date', '-slot__start_time')
    elif show == 'all':
        qs = qs.order_by('-slot__date', '-slot__start_time')
    else:
        show = 'upcoming'
        qs = qs.filter(status=Appointment.BOOKED).filter(_upcoming_q())
    if member_id.isdigit():
        qs = qs.filter(member_id=int(member_id))
    if date:
        qs = qs.filter(slot__date=date) if _valid_date(date) else qs
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="appointments.csv"'
        response.write('\\ufeff')
        writer = csv.writer(response)
        writer.writerow(['Member', 'Date', 'Start time', 'End time', 'Purpose',
                         'Book', 'Status', 'Note', 'Cancellation reason'])
        for appointment in qs:
            writer.writerow([
                appointment.member.name, appointment.slot.date.isoformat(),
                appointment.slot.start_time.strftime('%H:%M'),
                appointment.slot.end_time.strftime('%H:%M'),
                appointment.get_purpose_display(),
                appointment.book.title if appointment.book else '',
                appointment.get_status_display(), appointment.note,
                appointment.cancel_reason
            ])
        return response
    today = timezone.localdate()
    base = Appointment.objects.filter(status=Appointment.BOOKED).filter(_upcoming_q())
    return render(request, 'appointments/upcoming.html', {
        'appointments': qs, 'show': show, 'member_id': member_id, 'date': date,
        'members': Member.objects.all(),
        'today_count': base.filter(slot__date=today).count(),
        'week_count': base.filter(slot__date__lte=today + timedelta(days=7)).count(),
        'total_upcoming': base.count(),
    })
def my_appointments(request):
    """Show appointments belonging to the logged-in member only."""

    member = getattr(request.user, 'library_member', None)

    if not member:
        messages.error(request, 'Member profile not found.')
        return redirect('dashboard')

    show = request.GET.get('show', 'upcoming')

    qs = Appointment.objects.select_related(
        'member', 'slot', 'book'
    ).filter(member=member)

    if show == 'cancelled':
        qs = qs.filter(
            status=Appointment.CANCELLED
        ).order_by('-slot__date', '-slot__start_time')

    elif show == 'past':
        qs = qs.filter(
            status=Appointment.BOOKED
        ).exclude(
            _upcoming_q()
        ).order_by('-slot__date', '-slot__start_time')

    elif show == 'all':
        qs = qs.order_by('-slot__date', '-slot__start_time')

    else:
        show = 'upcoming'
        qs = qs.filter(
            status=Appointment.BOOKED
        ).filter(_upcoming_q()).order_by(
            'slot__date', 'slot__start_time'
        )

    return render(request, 'appointments/my_appointments.html', {
        'appointments': qs,
        'show': show,
    })

def _valid_date(value):
    from datetime import date
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False



def schedule(request):
    """Schedule Reservation for members and librarians."""

    member_profile = getattr(request.user, 'library_member', None)

    if member_profile and member_profile.status != Member.ACTIVE:
        messages.error(request, 'Your membership is inactive. You cannot schedule an appointment.')
        return redirect('dashboard')

    initial = {}

    if member_profile:
        initial['member'] = member_profile.pk
    elif request.GET.get('member', '').isdigit():
        initial['member'] = int(request.GET['member'])

    form = AppointmentForm(
        request.POST if request.method == 'POST' else None,
        initial=initial
    )

    # Hide member selection for Member accounts.
    if member_profile:
        form.fields['member'].queryset = Member.objects.filter(
            pk=member_profile.pk,
            status=Member.ACTIVE
        )
        form.fields['member'].widget = forms.HiddenInput()

    if request.method == 'POST':
        if form.is_valid():
            with transaction.atomic():
                d = form.cleaned_data

                selected_member = member_profile or d['member']

                appt = Appointment.objects.create(
                    member=selected_member,
                    slot=d['slot'],
                    purpose=d['purpose'],
                    book=d['book'],
                    note=d['note'].strip()
                )

            messages.success(
                request,
                f'Appointment scheduled for {appt.member.name} on {appt.slot}.'
            )

            if member_profile:
                return redirect('dashboard')

            return redirect('appointments:upcoming')

        messages.error(
            request,
            'Could not schedule the appointment. Please correct the errors below.'
        )

    return render(request, 'appointments/schedule.html', {
        'form': form
    })




@login_required
def cancel(request, pk):
    """Cancel an appointment. Members can only cancel their own."""

    member = getattr(request.user, 'library_member', None)

    appt = get_object_or_404(
        Appointment.objects.select_related('member', 'slot'),
        pk=pk
    )

    # Member can only cancel their own appointment.
    if member:
        if appt.member_id != member.pk:
            messages.error(request, 'You do not have permission to cancel this appointment.')
            return redirect('appointments:my_appointments')

    # Check appointment status.
    if appt.status != Appointment.BOOKED:
        messages.warning(request, 'This appointment is already cancelled.')
        return redirect(
            'appointments:my_appointments' if member
            else 'appointments:upcoming'
        )

    # Cannot cancel after appointment starts.
    if appt.slot.has_started():
        messages.error(
            request,
            'This appointment has already started or passed and cannot be cancelled.'
        )
        return redirect(
            'appointments:my_appointments' if member
            else 'appointments:upcoming'
        )

    form = CancelForm(
        request.POST if request.method == 'POST' else None
    )

    if request.method == 'POST':
        if form.is_valid():
            appt.status = Appointment.CANCELLED
            appt.cancelled_at = timezone.now()
            appt.cancel_reason = form.cleaned_data['reason'].strip()
            appt.save()

            messages.success(
                request,
                f'Appointment of {appt.member.name} on {appt.slot} has been cancelled.'
            )

            return redirect(
                'appointments:my_appointments' if member
                else 'appointments:upcoming'
            )

        messages.error(
            request,
            'Could not cancel. Please correct the errors below.'
        )

    return render(
        request,
        'appointments/cancel.html',
        {'appt': appt, 'form': form}
    )



def appointment_delete(request, pk):
    """Permanently remove a cancelled appointment record after confirmation."""
    appt = get_object_or_404(Appointment.objects.select_related('member', 'slot'), pk=pk)
    if appt.status != Appointment.CANCELLED:
        messages.error(request, 'Only cancelled appointments can be permanently deleted.')
        return redirect('appointments:upcoming')
    if request.method == 'POST':
        label = f'{appt.member.name} on {appt.slot}'
        appt.delete()
        messages.success(request, f'Cancelled appointment record ({label}) permanently deleted.')
        return redirect('appointments:upcoming')
    return render(request, 'appointments/confirm_delete.html', {'appt': appt})


# ------------------------------------------------------------------ Time slots
def slot_list(request):
    """Manage Time Slots (list / Retrieve)."""
    show = request.GET.get('show', 'upcoming')
    today = timezone.localdate()
    slots = TimeSlot.objects.annotate(
        booked=Count('appointments', filter=Q(appointments__status=Appointment.BOOKED)))
    if show == 'past':
        slots = slots.filter(date__lt=today).order_by('-date', '-start_time')
    elif show == 'all':
        slots = slots.order_by('-date', '-start_time')
    else:
        show = 'upcoming'
        slots = slots.filter(date__gte=today)
    return render(request, 'appointments/slot_list.html', {'slots': slots, 'show': show})


def slot_add(request):
    form = SlotForm(request.POST if request.method == 'POST' else None, initial={'capacity': 5, 'is_active': True})
    if request.method == 'POST':
        if form.is_valid():
            slot = form.save()
            messages.success(request, f'Time slot {slot} created successfully.')
            return redirect('appointments:slot_list')
        messages.error(request, 'Could not create the time slot. Please correct the errors below.')
    return render(request, 'appointments/slot_form.html', {'form': form, 'title': 'Add Time Slot'})


def slot_edit(request, pk):
    slot = get_object_or_404(TimeSlot, pk=pk)
    form = SlotForm(request.POST if request.method == 'POST' else None, instance=slot)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, f'Time slot {slot} updated successfully.')
            return redirect('appointments:slot_list')
        messages.error(request, 'Update failed. Please correct the errors below.')
    return render(request, 'appointments/slot_form.html', {'form': form, 'title': f'Edit Time Slot: {slot}', 'slot': slot})


@require_POST
def slot_toggle(request, pk):
    slot = get_object_or_404(TimeSlot, pk=pk)
    if slot.is_active:
        slot.is_active = False
        messages.success(request, f'Time slot {slot} closed for new bookings.')
    else:
        clash = TimeSlot.objects.filter(date=slot.date, is_active=True, start_time__lt=slot.end_time,
                                        end_time__gt=slot.start_time).exclude(pk=slot.pk)
        if slot.has_started():
            messages.error(request, 'This slot has already started and cannot be reopened.')
            return redirect('appointments:slot_list')
        if clash.exists():
            messages.error(request, f'Cannot reopen: it overlaps the active slot {clash.first()}.')
            return redirect('appointments:slot_list')
        slot.is_active = True
        messages.success(request, f'Time slot {slot} reopened.')
    slot.save()
    return redirect('appointments:slot_list')


def slot_delete(request, pk):
    slot = get_object_or_404(TimeSlot, pk=pk)
    if slot.appointments.exists():
        messages.error(request, f'Cannot delete {slot}: it has appointment records. Close it instead.')
        return redirect('appointments:slot_list')
    if request.method == 'POST':
        label = str(slot)
        slot.delete()
        messages.success(request, f'Time slot {label} deleted successfully.')
        return redirect('appointments:slot_list')
    return render(request, 'appointments/slot_confirm_delete.html', {'slot': slot})
