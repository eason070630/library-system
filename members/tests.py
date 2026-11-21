from django.test import TestCase
from django.urls import reverse

from .models import Member, MembershipType

def tier(name='Basic'):
    return MembershipType.objects.get(name=name)


VALID = {'name': 'Alice Tan', 'email': 'alice@example.com', 'phone': '012-3456789', 'address': 'KL'}


def valid(**kw):
    return dict(VALID, membership_type=tier().pk, **kw)


class MemberTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.client.force_login(get_user_model().objects.create_superuser('tester', 't@x.com', 'pw'))

    def test_register_valid(self):
        r = self.client.post(reverse('members:register'), valid(), follow=True)
        self.assertContains(r, 'registered successfully')
        self.assertEqual(Member.objects.get().phone, '0123456789')

    def test_register_invalid_name_phone_email(self):
        bad = dict(valid(), name='Al1ce', phone='12345', email='not-an-email')
        r = self.client.post(reverse('members:register'), bad)
        self.assertEqual(Member.objects.count(), 0)
        self.assertContains(r, 'only contain letters')
        self.assertContains(r, 'valid Malaysian mobile')
        self.assertContains(r, 'valid email')

    def test_duplicate_email(self):
        Member.objects.create(name='Bob', email='alice@example.com', phone='0123456789', membership_type=tier())
        r = self.client.post(reverse('members:register'), valid())
        self.assertContains(r, 'already registered')

    def test_update_own_email_ok_but_other_duplicate_blocked(self):
        a = Member.objects.create(name='Alice', email='a@x.com', phone='0123456789', membership_type=tier())
        Member.objects.create(name='Bob', email='b@x.com', phone='0123456780', membership_type=tier())
        ok = self.client.post(reverse('members:update', args=[a.pk]), valid(email='a@x.com'), follow=True)
        self.assertContains(ok, 'updated successfully')
        bad = self.client.post(reverse('members:update', args=[a.pk]), valid(email='b@x.com'))
        self.assertContains(bad, 'already registered')

    def test_deactivate_then_delete_flow(self):
        m = Member.objects.create(name='Alice', email='a@x.com', phone='0123456789', membership_type=tier())
        r = self.client.get(reverse('members:delete', args=[m.pk]), follow=True)
        self.assertContains(r, 'Only inactive members')
        self.client.post(reverse('members:deactivate', args=[m.pk]))
        m.refresh_from_db(); self.assertEqual(m.status, 'inactive')
        r = self.client.post(reverse('members:deactivate', args=[m.pk]), follow=True)
        self.assertContains(r, 'already inactive')
        r = self.client.post(reverse('members:delete', args=[m.pk]), follow=True)
        self.assertContains(r, 'deleted permanently')
        self.assertEqual(Member.objects.count(), 0)

    def test_history_without_borrowing_module(self):
        m = Member.objects.create(name='Alice', email='a@x.com', phone='0123456789', membership_type=tier())
        r = self.client.get(reverse('members:history', args=[m.pk]))
        self.assertContains(r, 'not connected yet')
        self.assertEqual(self.client.get(reverse('members:history', args=[999])).status_code, 404)


class TierTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.client.force_login(get_user_model().objects.create_superuser('tester', 't@x.com', 'pw'))

    def test_three_tiers_seeded_with_increasing_limits(self):
        tiers = list(MembershipType.objects.all())
        self.assertEqual([t.name for t in tiers], ['Basic', 'Silver', 'Gold'])
        self.assertTrue(tiers[0].max_books < tiers[1].max_books < tiers[2].max_books)
        self.assertTrue(tiers[0].loan_days < tiers[1].loan_days < tiers[2].loan_days)

    def test_tier_required_and_limits_exposed(self):
        bad = dict(VALID)  # no tier chosen
        r = self.client.post(reverse('members:register'), bad)
        self.assertContains(r, 'choose a membership tier')
        self.client.post(reverse('members:register'), dict(VALID, membership_type=tier('Gold').pk))
        m = Member.objects.get()
        self.assertEqual((m.max_books, m.loan_days), (10, 30))
        self.assertEqual(m.remaining_quota(), 10)
        self.assertTrue(m.can_borrow())
        m.status = 'inactive'
        self.assertFalse(m.can_borrow())

    def test_dashboard_and_tier_filter(self):
        Member.objects.create(name='G', email='g@x.com', phone='0123456789', membership_type=tier('Gold'))
        Member.objects.create(name='B', email='b@x.com', phone='0123456780', membership_type=tier('Basic'))
        r = self.client.get(reverse('home'))
        self.assertContains(r, 'Gold')
        r = self.client.get(reverse('members:list'), {'tier': tier('Gold').pk})
        self.assertContains(r, 'g@x.com')
        self.assertNotContains(r, 'b@x.com')
