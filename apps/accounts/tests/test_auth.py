from datetime import timedelta

from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts import otp
from apps.accounts.models import ClientProfile, OTPCode, User
from apps.core.tests.factories import make_catalog, make_user
from apps.providers.models import ProviderProfile

PWD = "Motdepasse-Solide9"


class AuthTestCase(TestCase):
    def setUp(self):
        cache.clear()  # remet à zéro les compteurs de rate limiting
        self.cat = make_catalog()


class ClientSignupTests(AuthTestCase):
    data = {
        "first_name": "Aïcha", "last_name": "Ngono", "email": "aicha@test.cm", "phone": "699 11 22 33",
        "password1": PWD, "password2": PWD, "accept_terms": "on",
    }

    def test_signup_creates_client_logs_in_and_sends_otp(self):
        resp = self.client.post(reverse("accounts:signup_client"), self.data)
        self.assertRedirects(resp, reverse("accounts:verify"))
        user = User.objects.get(email="aicha@test.cm")
        self.assertEqual(user.role, User.Role.CLIENT)
        self.assertEqual(user.phone, "699112233")
        self.assertTrue(ClientProfile.objects.filter(user=user).exists())
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(user.email_verified)

    def test_duplicate_email_rejected_case_insensitive(self):
        make_user(email="aicha@test.cm")
        resp = self.client.post(reverse("accounts:signup_client"), {**self.data, "email": "AICHA@test.cm"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "existe déjà")

    def test_duplicate_phone_rejected(self):
        make_user(phone="699112233")
        resp = self.client.post(reverse("accounts:signup_client"), self.data)
        self.assertContains(resp, "ce numéro")
        self.assertFalse(User.objects.filter(email="aicha@test.cm").exists())

    def test_weak_or_mismatched_password_rejected(self):
        resp = self.client.post(reverse("accounts:signup_client"), {**self.data, "password1": "12345678", "password2": "12345678"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(email="aicha@test.cm").exists())
        resp = self.client.post(reverse("accounts:signup_client"), {**self.data, "password2": "autre-chose-9X"})
        self.assertContains(resp, "ne correspondent pas")

    def test_terms_required(self):
        data = {k: v for k, v in self.data.items() if k != "accept_terms"}
        resp = self.client.post(reverse("accounts:signup_client"), data)
        self.assertContains(resp, "conditions")

    def test_authenticated_user_redirected_away_from_signup(self):
        user = make_user()
        self.client.force_login(user)
        self.assertRedirects(self.client.get(reverse("accounts:signup_client")), user.get_home_url())


class ProviderSignupTests(AuthTestCase):
    def data(self, **over):
        d = {
            "first_name": "Paul", "last_name": "Tchoumi", "email": "paul@test.cm", "whatsapp": "699 00 11 22",
            "business_name": "Plomberie Tchoumi", "activity_type": "FREELANCE", "category": self.cat["plomberie"].pk,
            "subcategories": [self.cat["plombier"].pk], "city": self.cat["city"].pk,
            "password1": PWD, "password2": PWD, "accept_terms": "on",
        }
        d.update(over)
        return d

    def test_signup_creates_pending_invisible_provider_with_trade(self):
        resp = self.client.post(reverse("accounts:signup_provider"), self.data())
        self.assertRedirects(resp, reverse("accounts:verify"))
        user = User.objects.get(email="paul@test.cm")
        self.assertEqual(user.role, User.Role.PROVIDER)
        profile = user.provider_profile
        self.assertEqual(profile.status, ProviderProfile.Status.PENDING)
        self.assertEqual(profile.category, self.cat["plomberie"])
        self.assertEqual(list(profile.subcategories.all()), [self.cat["plombier"]])
        self.assertFalse(profile.is_public)
        self.assertNotIn(profile, ProviderProfile.objects.public())
        # champs spécifiques du métier initialisés
        self.assertEqual(profile.field_values.count(), 1)

    def test_subcategory_must_belong_to_chosen_category(self):
        resp = self.client.post(reverse("accounts:signup_provider"), self.data(subcategories=[self.cat["couturier"].pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "doivent appartenir au métier choisi")
        self.assertFalse(User.objects.filter(email="paul@test.cm").exists())

    def test_trade_is_required(self):
        resp = self.client.post(reverse("accounts:signup_provider"), self.data(category=""))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(email="paul@test.cm").exists())

    def test_inactive_category_not_selectable(self):
        self.cat["plomberie"].is_active = False
        self.cat["plomberie"].save()
        resp = self.client.post(reverse("accounts:signup_provider"), self.data())
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(email="paul@test.cm").exists())

    def test_subcategory_fragment_filters_by_category(self):
        resp = self.client.get(reverse("accounts:subcategories"), {"category": self.cat["plomberie"].pk})
        self.assertContains(resp, "Plombier")
        self.assertNotContains(resp, "Couturier")
        resp = self.client.get(reverse("accounts:subcategories"), {"category": "abc"})
        self.assertContains(resp, "Choisissez d'abord")

    def test_signup_page_renders(self):
        self.assertEqual(self.client.get(reverse("accounts:signup_provider")).status_code, 200)
        self.assertEqual(self.client.get(reverse("accounts:signup")).status_code, 200)


class RoleRedirectAndPermissionTests(AuthTestCase):
    def setUp(self):
        super().setUp()
        from apps.core.tests.factories import make_provider
        self.client_user = make_user(User.Role.CLIENT, email="c@test.cm")
        self.admin = make_user(User.Role.ADMIN, email="a@test.cm")
        self.provider = make_provider(self.cat)
        self.provider_user = self.provider.user

    def login(self, user):
        return self.client.post(reverse("accounts:login"), {"username": user.email, "password": "pass12345"})

    def test_login_redirects_by_role(self):
        self.assertRedirects(self.login(self.client_user), reverse("core:client_home"))
        self.client.logout()
        self.assertRedirects(self.login(self.provider_user), reverse("dashboard_provider:home"))
        self.client.logout()
        self.assertRedirects(self.login(self.admin), reverse("dashboard_admin:home"))

    def test_login_honours_safe_next_url(self):
        resp = self.client.post(reverse("accounts:login") + "?next=/prestataire/", {"username": self.provider_user.email, "password": "pass12345", "next": "/prestataire/"})
        self.assertRedirects(resp, "/prestataire/")

    def test_login_rejects_external_next_url(self):
        resp = self.client.post(reverse("accounts:login"), {"username": self.client_user.email, "password": "pass12345", "next": "https://evil.example/"})
        self.assertRedirects(resp, reverse("core:client_home"))

    def test_anonymous_is_sent_to_login(self):
        for name in ("dashboard_provider:home", "dashboard_admin:home"):
            resp = self.client.get(reverse(name))
            self.assertEqual(resp.status_code, 302)
            self.assertIn(reverse("accounts:login"), resp["Location"])

    def test_client_cannot_access_provider_or_admin_space(self):
        self.client.force_login(self.client_user)
        for name in ("dashboard_provider:home", "dashboard_admin:home"):
            resp = self.client.get(reverse(name))
            self.assertRedirects(resp, reverse("core:client_home"), fetch_redirect_response=False)

    def test_provider_cannot_access_admin_space(self):
        self.client.force_login(self.provider_user)
        resp = self.client.get(reverse("dashboard_admin:home"))
        self.assertRedirects(resp, reverse("dashboard_provider:home"), fetch_redirect_response=False)

    def test_admin_cannot_access_provider_space(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("dashboard_provider:home"))
        self.assertRedirects(resp, reverse("dashboard_admin:home"), fetch_redirect_response=False)

    def test_each_role_reaches_own_space(self):
        for user, name in ((self.provider_user, "dashboard_provider:home"), (self.admin, "dashboard_admin:home")):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_deactivated_provider_cannot_login(self):
        self.provider_user.is_active = False
        self.provider_user.save()
        resp = self.login(self.provider_user)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)


class LoginRateLimitTests(AuthTestCase):
    def test_too_many_failures_blocks_even_correct_password(self):
        user = make_user(email="x@test.cm")
        for _ in range(5):
            self.client.post(reverse("accounts:login"), {"username": user.email, "password": "mauvais"})
        resp = self.client.post(reverse("accounts:login"), {"username": user.email, "password": "pass12345"})
        self.assertEqual(resp.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_success_resets_counter(self):
        user = make_user(email="x@test.cm")
        for _ in range(3):
            self.client.post(reverse("accounts:login"), {"username": user.email, "password": "mauvais"})
        self.client.post(reverse("accounts:login"), {"username": user.email, "password": "pass12345"})
        self.client.logout()
        for _ in range(4):
            self.client.post(reverse("accounts:login"), {"username": user.email, "password": "mauvais"})
        resp = self.client.post(reverse("accounts:login"), {"username": user.email, "password": "pass12345"})
        self.assertEqual(resp.status_code, 302)


class OTPTests(AuthTestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()

    def test_correct_code_verifies_email(self):
        code = otp.issue_otp(self.user, "email")
        self.assertEqual(otp.verify_otp(self.user, "email", code), otp.OTPResult.OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)

    def test_code_is_single_use(self):
        code = otp.issue_otp(self.user, "email")
        otp.verify_otp(self.user, "email", code)
        self.assertEqual(otp.verify_otp(self.user, "email", code), otp.OTPResult.MISSING)

    def test_code_not_stored_in_clear(self):
        code = otp.issue_otp(self.user, "email")
        self.assertNotIn(code, OTPCode.objects.get(user=self.user).code_hash)

    def test_wrong_code_then_lockout_after_max_attempts(self):
        code = otp.issue_otp(self.user, "email")
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(OTPCode.MAX_ATTEMPTS - 1):
            self.assertEqual(otp.verify_otp(self.user, "email", wrong), otp.OTPResult.WRONG)
        self.assertEqual(otp.verify_otp(self.user, "email", wrong), otp.OTPResult.LOCKED)
        self.assertEqual(otp.verify_otp(self.user, "email", code), otp.OTPResult.MISSING)  # même le bon code est invalidé

    def test_expired_code_rejected(self):
        code = otp.issue_otp(self.user, "email")
        OTPCode.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(otp.verify_otp(self.user, "email", code), otp.OTPResult.EXPIRED)

    def test_new_code_invalidates_previous_one(self):
        old = otp.issue_otp(self.user, "email")
        new = otp.issue_otp(self.user, "email")
        if old != new:
            self.assertEqual(otp.verify_otp(self.user, "email", old), otp.OTPResult.WRONG)
        self.assertEqual(otp.verify_otp(self.user, "email", new), otp.OTPResult.OK)

    def test_sms_channel_marks_phone_verified(self):
        user = make_user(phone="699000111")
        code = otp.issue_otp(user, "sms")
        self.assertEqual(otp.verify_otp(user, "sms", code), otp.OTPResult.OK)
        user.refresh_from_db()
        self.assertTrue(user.phone_verified)

    def test_verify_view_flow(self):
        self.client.force_login(self.user)
        code = otp.issue_otp(self.user, "email")
        resp = self.client.post(reverse("accounts:verify"), {"code": "123456" if code != "123456" else "654321"})
        self.assertContains(resp, "Code incorrect")
        resp = self.client.post(reverse("accounts:verify"), {"code": code})
        self.assertRedirects(resp, self.user.get_home_url())
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)

    def test_verify_requires_login(self):
        resp = self.client.get(reverse("accounts:verify"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("accounts:login"), resp["Location"])

    def test_resend_is_rate_limited(self):
        self.client.force_login(self.user)
        for _ in range(3):
            self.client.post(reverse("accounts:verify_resend"))
        mail.outbox.clear()
        self.client.post(reverse("accounts:verify_resend"))
        self.assertEqual(len(mail.outbox), 0)


class PasswordResetTests(AuthTestCase):
    def test_reset_email_sent_for_known_address_only(self):
        make_user(email="known@test.cm")
        self.client.post(reverse("accounts:password_reset"), {"email": "known@test.cm"})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/compte/mot-de-passe/reinitialiser/", mail.outbox[0].body)
        resp = self.client.post(reverse("accounts:password_reset"), {"email": "unknown@test.cm"})
        self.assertRedirects(resp, reverse("accounts:password_reset_done"))  # même réponse : pas d'énumération
        self.assertEqual(len(mail.outbox), 1)

    def test_full_reset_flow(self):
        user = make_user(email="known@test.cm")
        self.client.post(reverse("accounts:password_reset"), {"email": "known@test.cm"})
        link = next(l for l in mail.outbox[0].body.splitlines() if "/reinitialiser/" in l)
        path = "/" + link.split("://", 1)[1].split("/", 1)[1]
        resp = self.client.get(path, follow=True)
        resp = self.client.post(resp.request["PATH_INFO"], {"new_password1": "Nouveau-Pass-77", "new_password2": "Nouveau-Pass-77"})
        self.assertRedirects(resp, reverse("accounts:password_reset_complete"))
        self.assertTrue(self.client.login(username="known@test.cm", password="Nouveau-Pass-77"))
