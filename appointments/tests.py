from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from categories.models import Book
from members.models import Member, MembershipType

from .models import Appointment, TimeSlot


def tomorrow(n=1):
    return timezone.localdate() + timedelta(days=n)


def slot(d=None, h=10, cap=2, **kw):
    d = d or tomorrow()
    return TimeSlot.objects.create(date=d, start_time=time(h, 0), end_time=time(h + 1, 0), capacity=cap, **kw)


def member(name='Alice Tan', tier='Basic', email=None):
    return Member.objects.create(name=name, email=email or f'{name.split()[0].lower()}@x.com', phone='0123456789',
                                 membership_type=MembershipType.objects.get(name=tier))


class Base(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser('tester', 't@x.com', 'pw'))

    def book(self, m, s, purpose='consult', **kw):
        data = {'member': m.pk, 'slot': s.pk, 'purpose': purpose, 'note': ''}
        data.update(kw)
        return self.client.post(reverse('appointments:schedule'), data, follow=True)


class ScheduleTests(Base):
    def test_schedule_valid(self):
        m, s = member(), slot()
        r = self.book(m, s)
        self.assertContains(r, 'Appointment scheduled')
        self.assertEqual(Appointment.objects.get().member, m)

    def test_required_fields(self):
        r = self.client.post(reverse('appointments:schedule'), {})
        for msg in ('select a member', 'select a time slot', 'choose a purpose'):
            self.assertContains(r, msg)

    def test_pickup_needs_book_and_book_only_for_pickup(self):
        m, s = member(), slot()
        self.assertContains(self.book(m, s, purpose='pickup'), 'choose the book to pick up')
        b = Book.objects.create(title='Dune', author='Frank Herbert', isbn='9780441172719')
        self.assertContains(self.book(m, s, purpose='tour', book=b.pk), 'only be chosen for a')
        self.assertContains(self.book(m, s, purpose='pickup', book=b.pk), 'Appointment scheduled')
        self.assertEqual(Appointment.objects.get().book, b)

    def test_slot_full(self):
        s = slot(cap=1)
        self.book(member('Alice Tan'), s)
        self.assertContains(self.book(member('Bob Lim'), s), 'time slot is full')

    def test_duplicate_and_overlap(self):
        m, s = member(), slot(h=10)
        self.book(m, s)
        self.assertContains(self.book(m, s), 'already booked this time slot')
        overlap = TimeSlot.objects.create(date=s.date, start_time=time(10, 30), end_time=time(11, 30), capacity=2)
        self.assertContains(self.book(m, overlap), 'overlaps')

    def test_limit_depends_on_tier(self):
        basic, gold = member('Bob Lim', 'Basic'), member('Gina Goh', 'Gold')
        for i in range(2):
            self.assertContains(self.book(basic, slot(tomorrow(i + 1))), 'Appointment scheduled')
        self.assertContains(self.book(basic, slot(tomorrow(5))), 'at most 2')
        for i in range(4):
            self.assertContains(self.book(gold, slot(tomorrow(i + 10))), 'Appointment scheduled')
        self.assertContains(self.book(gold, slot(tomorrow(20))), 'at most 4')

    def test_inactive_member_and_closed_slot_not_offered(self):
        m = member(); m.status = 'inactive'; m.save()
        s = slot(is_active=False)
        r = self.book(m, s)
        self.assertContains(r, 'does not exist or is inactive')
        self.assertContains(r, 'not available')

    def test_past_slot_rejected(self):
        m = member()
        past = TimeSlot.objects.create(date=timezone.localdate() - timedelta(days=1),
                                       start_time=time(9, 0), end_time=time(10, 0), capacity=2)
        self.assertEqual(Appointment.objects.count(), 0)
        self.assertContains(self.book(m, past), 'not available')   # past dates are not in the choice list


class CancelAndUpcomingTests(Base):
    def test_cancel_flow(self):
        m, s = member(), slot()
        self.book(m, s)
        a = Appointment.objects.get()
        self.assertContains(self.client.get(reverse('appointments:cancel', args=[a.pk])), 'Keep it')
        self.assertContains(self.client.post(reverse('appointments:cancel', args=[a.pk]), {'reason': 'x' * 201}),
                            '200 characters or fewer')
        r = self.client.post(reverse('appointments:cancel', args=[a.pk]), {'reason': 'Sick'}, follow=True)
        self.assertContains(r, 'has been cancelled')
        a.refresh_from_db()
        self.assertEqual((a.status, a.cancel_reason), ('cancelled', 'Sick'))
        self.assertIsNotNone(a.cancelled_at)
        self.assertContains(self.client.get(reverse('appointments:cancel', args=[a.pk]), follow=True), 'already cancelled')
        self.assertEqual(s.seats_left, 2)   # seat is freed

    def test_cannot_cancel_started(self):
        m = member()
        old = TimeSlot.objects.create(date=timezone.localdate() - timedelta(days=1), start_time=time(9, 0),
                                      end_time=time(10, 0), capacity=2)
        a = Appointment.objects.create(member=m, slot=old, purpose='tour')
        r = self.client.post(reverse('appointments:cancel', args=[a.pk]), follow=True)
        self.assertContains(r, 'cannot be cancelled')

    def test_upcoming_tabs_and_filters(self):
        m1, m2 = member('Alice Tan'), member('Bob Lim')
        self.book(m1, slot(tomorrow(1)))
        self.book(m2, slot(tomorrow(2)))
        old_slot = TimeSlot.objects.create(date=timezone.localdate() - timedelta(days=2), start_time=time(9, 0),
                                           end_time=time(10, 0), capacity=2)
        Appointment.objects.create(member=m1, slot=old_slot, purpose='tour')
        ALICE, BOB = '>Alice Tan <span', '>Bob Lim <span'   # table cells (the filter dropdown also lists names)
        r = self.client.get(reverse('appointments:upcoming'))
        self.assertContains(r, ALICE); self.assertContains(r, BOB)
        self.assertNotContains(r, 'Library tour')          # the past appointment is not in the upcoming tab
        past = self.client.get(reverse('appointments:upcoming'), {'show': 'past'})
        self.assertContains(past, ALICE); self.assertNotContains(past, BOB)
        only_bob = self.client.get(reverse('appointments:upcoming'), {'member': m2.pk})
        self.assertNotContains(only_bob, ALICE); self.assertContains(only_bob, BOB)
        self.client.post(reverse('appointments:cancel', args=[Appointment.objects.filter(member=m2).first().pk]))
        cancelled = self.client.get(reverse('appointments:upcoming'), {'show': 'cancelled'})
        self.assertContains(cancelled, BOB); self.assertNotContains(cancelled, ALICE)
        self.assertEqual(self.client.get(reverse('appointments:upcoming'), {'date': 'junk'}).status_code, 200)


class SlotTests(Base):
    def post(self, **kw):
        data = {'date': tomorrow().isoformat(), 'start_time': '10:00', 'end_time': '11:00',
                'capacity': 5, 'note': '', 'is_active': 'on'}
        data.update(kw)
        return self.client.post(reverse('appointments:slot_add'), data, follow=True)

    def test_create_valid(self):
        self.assertContains(self.post(), 'created successfully')
        self.assertEqual(TimeSlot.objects.count(), 1)

    def test_validation(self):
        self.assertContains(self.post(date=(timezone.localdate() - timedelta(days=1)).isoformat()), 'cannot be in the past')
        self.assertContains(self.post(end_time='09:00'), 'End time must be after')
        self.assertContains(self.post(end_time='10:10'), 'at least 15 minutes')
        self.assertContains(self.post(start_time='07:00'), 'opening hours')
        self.assertContains(self.post(end_time='21:00'), 'opening hours')
        self.assertContains(self.post(capacity=0), 'between 1 and 20')
        self.assertContains(self.post(capacity=99), 'between 1 and 20')
        r = self.client.post(reverse('appointments:slot_add'), {})
        self.assertContains(r, 'This field is required')
        self.assertEqual(TimeSlot.objects.count(), 0)

    def test_overlap_and_duplicate(self):
        self.post()
        self.assertContains(self.post(start_time='10:30', end_time='11:30'), 'overlaps')
        self.assertEqual(TimeSlot.objects.count(), 1)
        self.assertContains(self.post(start_time='11:00', end_time='12:00'), 'created successfully')

    def test_edit_capacity_cannot_drop_below_booked(self):
        s = slot(cap=3)
        self.book(member('Alice Tan'), s); self.book(member('Bob Lim'), s)
        r = self.client.post(reverse('appointments:slot_edit', args=[s.pk]), {
            'date': s.date.isoformat(), 'start_time': '10:00', 'end_time': '11:00', 'capacity': 1, 'is_active': 'on'})
        self.assertContains(r, 'capacity cannot be lower')
        r = self.client.post(reverse('appointments:slot_edit', args=[s.pk]), {
            'date': s.date.isoformat(), 'start_time': '10:00', 'end_time': '11:00', 'capacity': 4, 'is_active': 'on'}, follow=True)
        self.assertContains(r, 'updated successfully')

    def test_close_reopen_delete_rules(self):
        s = slot()
        self.client.post(reverse('appointments:slot_toggle', args=[s.pk]))
        s.refresh_from_db(); self.assertFalse(s.is_active)
        self.client.post(reverse('appointments:slot_toggle', args=[s.pk]))
        s.refresh_from_db(); self.assertTrue(s.is_active)
        m = member()
        s.is_active = True; s.save()
        self.book(m, s)
        r = self.client.post(reverse('appointments:slot_delete', args=[s.pk]), follow=True)
        self.assertContains(r, 'has appointment records')
        empty = slot(h=15)
        r = self.client.post(reverse('appointments:slot_delete', args=[empty.pk]), follow=True)
        self.assertContains(r, 'deleted successfully')

    def test_list_pages(self):
        slot()
        for show in ('upcoming', 'past', 'all'):
            self.assertEqual(self.client.get(reverse('appointments:slot_list'), {'show': show}).status_code, 200)


class MemberIntegrationTests(Base):
    def test_member_with_upcoming_appointment_cannot_be_deactivated(self):
        m = member(); self.book(m, slot())
        r = self.client.post(reverse('members:deactivate', args=[m.pk]), follow=True)
        self.assertContains(r, 'upcoming appointments')
        m.refresh_from_db(); self.assertEqual(m.status, 'active')

    def test_member_with_appointment_history_cannot_be_deleted(self):
        m = member(); s = slot(); self.book(m, s)
        a = Appointment.objects.get(); a.status = 'cancelled'; a.save()
        m.status = 'inactive'; m.save()
        r = self.client.post(reverse('members:delete', args=[m.pk]), follow=True)
        self.assertContains(r, 'appointment records')
        self.assertTrue(Member.objects.filter(pk=m.pk).exists())
