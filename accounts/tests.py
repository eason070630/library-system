import re
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from .models import AccessRight, AuditLog, Role, UserProfile
from .rights import ALL_CODES

User = get_user_model()


def make_user(username, role_name, password='Str0ngPass!x', **kw):
    u = User.objects.create_user(username, f'{username}@x.com', password, first_name=username.title(), **kw)
    UserProfile.objects.create(user=u, role=Role.objects.get(name=role_name))
    return u


class SeedTests(TestCase):
    def test_rights_and_default_roles_exist(self):
        self.assertEqual(set(AccessRight.objects.values_list('code', flat=True)), set(ALL_CODES))
        self.assertEqual(list(Role.objects.values_list('name', flat=True)), ['Administrator', 'Librarian', 'Assistant'])
        admin = Role.objects.get(name='Administrator')
        self.assertEqual(admin.rights.count(), len(ALL_CODES))


class LoginAndAccessTests(TestCase):
    def test_login_required_redirect(self):
        r = self.client.get(reverse('members:list'))
        self.assertRedirects(r, f"{reverse('accounts:login')}?next=/members/", fetch_redirect_response=False)

    def test_login_success_and_failure_are_audited(self):
        make_user('lib', 'Librarian')
        bad = self.client.post(reverse('accounts:login'), {'username': 'lib', 'password': 'wrong'})
        self.assertContains(bad, 'correct username and password')
        ok = self.client.post(reverse('accounts:login'), {'username': 'lib', 'password': 'Str0ngPass!x'})
        self.assertEqual(ok.status_code, 302)
        actions = list(AuditLog.objects.filter(username='lib').values_list('action', flat=True))
        self.assertIn('login_failed', actions)
        self.assertIn('login', actions)

    def test_role_permissions_enforced(self):
        make_user('assist', 'Assistant')
        self.client.login(username='assist', password='Str0ngPass!x')
        self.assertEqual(self.client.get(reverse('members:list')).status_code, 200)         # members.view
        self.assertEqual(self.client.get(reverse('members:register')).status_code, 403)     # needs members.manage
        self.assertEqual(self.client.get(reverse('appointments:schedule')).status_code, 200)  # appointments.manage
        self.assertEqual(self.client.get(reverse('accounts:account_list')).status_code, 403)
        self.assertEqual(self.client.get(reverse('accounts:audit_log')).status_code, 403)

    def test_librarian_can_audit_but_not_manage_accounts(self):
        make_user('lib', 'Librarian')
        self.client.login(username='lib', password='Str0ngPass!x')
        self.assertEqual(self.client.get(reverse('accounts:audit_log')).status_code, 200)
        self.assertEqual(self.client.get(reverse('accounts:role_list')).status_code, 403)

    def test_setup_only_when_no_users(self):
        r = self.client.post(reverse('accounts:setup'), {
            'username': 'boss', 'full_name': 'Big Boss', 'email': 'boss@x.com',
            'password1': 'Str0ngPass!x', 'password2': 'Str0ngPass!x'}, follow=True)
        self.assertContains(r, 'first administrator')
        self.assertTrue(User.objects.get(username='boss').profile.role.name == 'Administrator')
        self.client.logout()
        r = self.client.get(reverse('accounts:setup'), follow=True)
        self.assertContains(r, 'Setup is already done')

    def test_setup_validation(self):
        r = self.client.post(reverse('accounts:setup'), {
            'username': '1x', 'full_name': 'B', 'email': 'bad', 'password1': '123', 'password2': '456'})
        self.assertContains(r, 'Username must be 4-30')
        self.assertContains(r, 'do not match')
        self.assertFalse(User.objects.exists())



class PublicRegistrationTests(TestCase):
    def test_landing_page_is_public_and_registration_creates_login_and_member(self):
        from members.models import Member, MembershipType
        self.assertEqual(self.client.get(reverse('home')).status_code, 200)
        tier = MembershipType.objects.get(name='Basic')
        response = self.client.post(reverse('accounts:register'), {
            'username': 'reader1', 'full_name': 'Reader One', 'email': 'reader1@example.com',
            'phone': '0123456789', 'address': 'Library Street',
            'membership_type': tier.pk,
            'password1': 'Str0ngPass!x', 'password2': 'Str0ngPass!x',
        }, follow=True)
        self.assertContains(response, 'Registration successful')
        user = User.objects.get(username='reader1')
        self.assertTrue(user.check_password('Str0ngPass!x'))
        member = Member.objects.get(user=user)
        self.assertEqual(member.email, user.email)
        self.assertFalse(hasattr(user, 'profile'))
        self.assertTrue(self.client.login(username='reader1', password='Str0ngPass!x'))
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)

    def test_registration_rejects_mismatched_passwords(self):
        from members.models import MembershipType
        response = self.client.post(reverse('accounts:register'), {
            'username': 'reader2', 'full_name': 'Reader Two', 'email': 'reader2@example.com',
            'phone': '0123456789', 'address': '',
            'membership_type': MembershipType.objects.get(name='Basic').pk,
            'password1': 'Str0ngPass!x', 'password2': 'DifferentPass!x',
        })
        self.assertContains(response, 'do not match')
        self.assertFalse(User.objects.filter(username='reader2').exists())


class AccountManagementTests(TestCase):
    def setUp(self):
        self.admin = make_user('boss', 'Administrator')
        self.client.login(username='boss', password='Str0ngPass!x')

    def test_admin_can_edit_a_registered_member_account_and_assign_a_role(self):
        from members.models import Member, MembershipType
        tier = MembershipType.objects.get(name='Basic')
        member_user = User.objects.create_user('reader1', 'reader1@x.com', 'Str0ngPass!x',
                                                first_name='Reader One')
        Member.objects.create(user=member_user, name='Reader One', email='reader1@x.com',
                              phone='0123456789', membership_type=tier)
        r = self.client.post(reverse('accounts:account_edit', args=[member_user.pk]), {
            'full_name': 'Reader One', 'email': 'reader1@x.com',
            'role': Role.objects.get(name='Assistant').pk}, follow=True)
        self.assertContains(r, 'updated successfully')
        member_user.refresh_from_db()
        self.assertEqual(member_user.profile.role.name, 'Assistant')

    def test_change_role_and_last_admin_protected(self):
        u = User.objects.create_user('second', 's@x.com', 'Str0ngPass!x', first_name='Second')
        UserProfile.objects.create(user=u, role=Role.objects.get(name='Assistant'))
        url = reverse('accounts:account_edit', args=[u.pk])
        r = self.client.post(url, {'full_name': 'Second One', 'email': 's@x.com',
                                   'role': Role.objects.get(name='Librarian').pk}, follow=True)
        self.assertContains(r, 'updated successfully')
        u.profile.refresh_from_db(); self.assertEqual(u.profile.role.name, 'Librarian')
        # the only administrator cannot be demoted
        r = self.client.post(reverse('accounts:account_edit', args=[self.admin.pk]), {
            'full_name': 'Boss', 'email': 'boss@x.com', 'role': Role.objects.get(name='Assistant').pk})
        self.assertContains(r, 'last administrator')

    def test_deactivate_rules(self):
        r = self.client.post(reverse('accounts:account_toggle', args=[self.admin.pk]), follow=True)
        self.assertContains(r, 'cannot deactivate your own')
        u = make_user('worker', 'Assistant')
        self.client.post(reverse('accounts:account_toggle', args=[u.pk]))
        u.refresh_from_db(); self.assertFalse(u.is_active)
        self.client.logout()
        self.assertFalse(self.client.login(username='worker', password='Str0ngPass!x'))

    def test_permanently_delete_account_and_keep_audit_record(self):
        u = make_user('remove_me', 'Assistant')
        confirm = self.client.get(reverse('accounts:account_delete', args=[u.pk]))
        self.assertEqual(confirm.status_code, 200)
        result = self.client.post(reverse('accounts:account_delete', args=[u.pk]), follow=True)
        self.assertContains(result, 'permanently deleted')
        self.assertFalse(User.objects.filter(pk=u.pk).exists())
        self.assertTrue(AuditLog.objects.filter(action='account_delete', target='User: remove_me').exists())

    def test_cannot_delete_self_or_last_administrator(self):
        self.client.post(reverse('accounts:account_delete', args=[self.admin.pk]), follow=True)
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())
        other_admin = make_user('otherboss', 'Administrator')
        self.client.post(reverse('accounts:account_delete', args=[self.admin.pk]), follow=True)
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())
        self.client.post(reverse('accounts:account_delete', args=[other_admin.pk]), follow=True)
        self.assertTrue(User.objects.filter(pk=other_admin.pk).exists())

    def test_admin_reset_password(self):
        u = make_user('worker', 'Assistant')
        r = self.client.post(reverse('accounts:account_reset_password', args=[u.pk]), follow=True)
        pw = re.search(r'Temporary password: (\w+)', r.content.decode()).group(1)
        u.refresh_from_db()
        self.assertTrue(u.check_password(pw))
        self.assertTrue(u.profile.must_change_password)
        self.assertFalse(u.check_password('Str0ngPass!x'))


class PasswordRecoveryTests(TestCase):
    def setUp(self):
        self.user = make_user('reader', 'Assistant')

    def test_full_recovery_flow(self):
        r = self.client.post(reverse('accounts:forgot'), {'identifier': 'reader@x.com'})
        self.assertContains(r, 'reset link has been sent')
        self.assertEqual(len(mail.outbox), 1)
        link = re.search(r'/accounts/reset/[\w-]+/[\w-]+/', mail.outbox[0].body).group(0)
        page = self.client.get(link)
        self.assertEqual(page.status_code, 200)
        bad = self.client.post(link, {'new_password1': 'short', 'new_password2': 'short'})
        self.assertContains(bad, 'too short')
        mismatch = self.client.post(link, {'new_password1': 'Another-Pw-77', 'new_password2': 'Different-77x'})
        self.assertContains(mismatch, 'do not match')
        ok = self.client.post(link, {'new_password1': 'Another-Pw-77', 'new_password2': 'Another-Pw-77'}, follow=True)
        self.assertContains(ok, 'password has been reset')
        self.assertTrue(self.client.login(username='reader', password='Another-Pw-77'))
        # the link works only once
        self.assertEqual(self.client.get(link).status_code, 400)

    def test_unknown_account_gets_same_message_and_no_email(self):
        r = self.client.post(reverse('accounts:forgot'), {'identifier': 'nobody'})
        self.assertContains(r, 'reset link has been sent')
        self.assertEqual(len(mail.outbox), 0)

    def test_bad_token(self):
        self.assertEqual(self.client.get('/accounts/reset/AAAA/bad-token/').status_code, 400)

    def test_empty_identifier(self):
        self.assertContains(self.client.post(reverse('accounts:forgot'), {'identifier': ''}), 'enter your username or email')


class RolePermissionTests(TestCase):
    def setUp(self):
        make_user('boss', 'Administrator')
        self.client.login(username='boss', password='Str0ngPass!x')
        self.rights = {r.code: r.pk for r in AccessRight.objects.all()}

    def test_create_and_edit_role_logs_changes(self):
        r = self.client.post(reverse('accounts:role_create'), {
            'name': 'Auditor', 'description': 'Read only', 'rights': [self.rights['audit.view']]}, follow=True)
        self.assertContains(r, 'saved successfully')
        role = Role.objects.get(name='Auditor')
        self.assertEqual(list(role.rights.values_list('code', flat=True)), ['audit.view'])
        self.client.post(reverse('accounts:role_edit', args=[role.pk]), {
            'name': 'Auditor', 'description': 'Read only', 'rights': [self.rights['members.view']]})
        log = AuditLog.objects.filter(action='permissions').first()
        self.assertIn('granted: members.view', log.detail)
        self.assertIn('revoked: audit.view', log.detail)

    def test_role_validation(self):
        self.assertContains(self.client.post(reverse('accounts:role_create'), {'name': 'Librarian'}), 'already exists')
        self.assertContains(self.client.post(reverse('accounts:role_create'), {'name': '!!'}), 'at least 3 characters')

    def test_administrator_role_protected(self):
        admin = Role.objects.get(name='Administrator')
        r = self.client.post(reverse('accounts:role_edit', args=[admin.pk]), {
            'name': 'Administrator', 'rights': [self.rights['members.view']]})
        self.assertContains(r, 'must keep')
        r = self.client.post(reverse('accounts:role_edit', args=[admin.pk]), {
            'name': 'Boss', 'rights': list(self.rights.values())})
        self.assertContains(r, 'cannot be renamed')
        r = self.client.post(reverse('accounts:role_delete', args=[admin.pk]), follow=True)
        self.assertContains(r, 'cannot be deleted')

    def test_cannot_delete_role_in_use(self):
        r = self.client.post(reverse('accounts:role_delete', args=[Role.objects.get(name='Administrator').pk]), follow=True)
        lib = Role.objects.get(name='Librarian'); make_user('lib', 'Librarian')
        r = self.client.post(reverse('accounts:role_delete', args=[lib.pk]), follow=True)
        self.assertContains(r, 'still use it')
        unused = Role.objects.create(name='Temp')
        r = self.client.post(reverse('accounts:role_delete', args=[unused.pk]), follow=True)
        self.assertContains(r, 'deleted successfully')

    def test_permission_change_takes_effect(self):
        make_user('assist', 'Assistant')
        assistant = Role.objects.get(name='Assistant')
        c2 = self.client_class(); c2.login(username='assist', password='Str0ngPass!x')
        self.assertEqual(c2.get(reverse('members:register')).status_code, 403)
        assistant.rights.add(AccessRight.objects.get(code='members.manage'))
        self.assertEqual(c2.get(reverse('members:register')).status_code, 200)


class AuditLogTests(TestCase):
    def setUp(self):
        make_user('boss', 'Administrator')
        self.client.login(username='boss', password='Str0ngPass!x')

    def test_data_changes_are_logged_with_actor_and_diff(self):
        from members.models import Member, MembershipType
        self.client.post(reverse('members:register'), {
            'name': 'Alice Tan', 'email': 'a@x.com', 'phone': '0123456789', 'address': '',
            'membership_type': MembershipType.objects.get(name='Basic').pk})
        m = Member.objects.get()
        self.client.post(reverse('members:update', args=[m.pk]), {
            'name': 'Alice Lim', 'email': 'a@x.com', 'phone': '0123456789', 'address': '',
            'membership_type': m.membership_type_id})
        self.client.post(reverse('members:deactivate', args=[m.pk]))
        logs = AuditLog.objects.filter(username='boss', target__startswith='Member:')
        self.assertTrue(logs.filter(action='create').exists())
        upd = logs.filter(action='update')
        self.assertTrue(any("'Alice Tan' -> 'Alice Lim'" in l.detail for l in upd))
        self.assertTrue(any("'active' -> 'inactive'" in l.detail for l in upd))

    def test_password_hash_never_logged(self):
        u = User.objects.get(username='boss'); u.set_password('Another-Pw-77'); u.save()
        self.assertFalse(AuditLog.objects.filter(detail__icontains='pbkdf2').exists())

    def test_view_filter_and_csv(self):
        r = self.client.get(reverse('accounts:audit_log'), {'action': 'login'})
        self.assertEqual(r.status_code, 200)
        r = self.client.get(reverse('accounts:audit_log'), {'from': 'garbage'})
        self.assertContains(r, 'Ignored invalid date')
        r = self.client.get(reverse('accounts:audit_log'), {'export': 'csv'})
        self.assertEqual(r['Content-Type'], 'text/csv')
        self.assertIn('Time,User,Action', r.content.decode())

    def test_pagination_pages_render(self):
        for i in range(60):
            AuditLog.objects.create(username='x', action='create', target=f'T{i}')
        self.assertContains(self.client.get(reverse('accounts:audit_log')), 'Page 1 of')
        self.assertContains(self.client.get(reverse('accounts:audit_log'), {'page': 2}), 'Previous')
        self.assertEqual(self.client.get(reverse('accounts:audit_log'), {'page': 3}).status_code, 200)
