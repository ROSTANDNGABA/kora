from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User


class UserModelTests(TestCase):
    def test_create_user_normalizes_email_and_phone(self):
        u = User.objects.create_user("Awa@Kora.CM", "pass12345", phone="6 99 00 11 22")
        self.assertEqual(u.email, "awa@kora.cm")
        self.assertEqual(u.phone, "699001122")
        self.assertEqual(u.role, User.Role.CLIENT)
        self.assertTrue(u.check_password("pass12345"))

    def test_empty_phone_stored_as_null_so_unique_holds(self):
        User.objects.create_user("a@kora.cm", "pass12345")
        User.objects.create_user("b@kora.cm", "pass12345")  # deux comptes sans téléphone
        self.assertEqual(User.objects.filter(phone__isnull=True).count(), 2)

    def test_superuser_gets_admin_role(self):
        u = User.objects.create_superuser("root@kora.cm", "pass12345")
        self.assertEqual(u.role, User.Role.ADMIN)
        self.assertTrue(u.is_staff and u.is_superuser)

    def test_home_url_depends_on_role(self):
        expected = {
            User.Role.CLIENT: reverse("core:client_home"),
            User.Role.PROVIDER: reverse("dashboard_provider:home"),
            User.Role.ADMIN: reverse("dashboard_admin:home"),
        }
        for role, url in expected.items():
            self.assertEqual(User(email=f"{role}@kora.cm", role=role).get_home_url(), url)


class LoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("client@kora.cm", "pass12345", phone="+237 699 00 11 22")

    def test_login_with_email(self):
        self.assertTrue(self.client.login(username="client@kora.cm", password="pass12345"))

    def test_login_with_email_case_insensitive(self):
        self.assertTrue(self.client.login(username="CLIENT@kora.cm", password="pass12345"))

    def test_login_with_phone(self):
        self.assertTrue(self.client.login(username="+237 699 00 11 22", password="pass12345"))

    def test_wrong_password_rejected(self):
        self.assertFalse(self.client.login(username="client@kora.cm", password="nope"))

    def test_unknown_identifier_rejected(self):
        self.assertFalse(self.client.login(username="inconnu@kora.cm", password="pass12345"))

    def test_login_view_redirects_to_role_home(self):
        resp = self.client.post(reverse("accounts:login"), {"username": "client@kora.cm", "password": "pass12345"})
        self.assertRedirects(resp, reverse("core:client_home"))

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save()
        self.assertFalse(self.client.login(username="client@kora.cm", password="pass12345"))
