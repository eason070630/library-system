from datetime import datetime

from django.db import models
from django.utils import timezone


def now_local():
    """Current local (Asia/Kuala_Lumpur) time as a naive datetime, comparable with slot dates/times."""
    return timezone.localtime().replace(tzinfo=None)


class TimeSlot(models.Model):
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    capacity = models.PositiveSmallIntegerField(default=5, help_text='How many members can book this slot (1-20)')
    note = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True, help_text='Untick to stop new bookings')

    class Meta:
        ordering = ['date', 'start_time']
        constraints = [models.UniqueConstraint(fields=['date', 'start_time'], name='uniq_slot_date_start')]

    def __str__(self):
        return f'{self.date:%d %b %Y} {self.start_time:%H:%M}-{self.end_time:%H:%M}'

    @property
    def start_dt(self):
        return datetime.combine(self.date, self.start_time)

    def has_started(self):
        return self.start_dt <= now_local()

    @property
    def booked_count(self):
        if hasattr(self, 'booked'):          # set by annotate() in list views
            return self.booked
        return self.appointments.filter(status=Appointment.BOOKED).count()

    @property
    def seats_left(self):
        return max(self.capacity - self.booked_count, 0)


class Appointment(models.Model):
    BOOKED = 'booked'
    CANCELLED = 'cancelled'
    STATUS_CHOICES = [(BOOKED, 'Booked'), (CANCELLED, 'Cancelled')]

    PICKUP, CONSULT, STUDY, TOUR = 'pickup', 'consult', 'study', 'tour'
    PURPOSE_CHOICES = [
        (PICKUP, 'Book pickup'),
        (CONSULT, 'Librarian consultation'),
        (STUDY, 'Study room'),
        (TOUR, 'Library tour'),
    ]

    member = models.ForeignKey('members.Member', on_delete=models.PROTECT, related_name='appointments')
    slot = models.ForeignKey(TimeSlot, on_delete=models.PROTECT, related_name='appointments')
    purpose = models.CharField(max_length=10, choices=PURPOSE_CHOICES)
    book = models.ForeignKey('categories.Book', null=True, blank=True, on_delete=models.SET_NULL,
                             related_name='appointments')
    note = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=BOOKED)
    created_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['slot__date', 'slot__start_time']

    def __str__(self):
        return f'{self.member.name} @ {self.slot}'

    @property
    def is_upcoming(self):
        return self.status == self.BOOKED and not self.slot.has_started()
