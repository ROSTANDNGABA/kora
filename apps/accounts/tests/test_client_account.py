import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.accounts.models import ClientProfile, User
from apps.core.tests.factories import make_catalog, make_provider, make_request, make_user
from apps.favorites.models import Favorite
from apps.requests_app.models import ServiceRequest
from apps.reviews.models import Review


def png(name="me.png"):
    buf = io.BytesIO()
    Image.new("RGB", (30, 30), "green").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


class ProfileTests(TestCase):
    def setUp(self):
        self.cat = make_catalog()
        self.user = make_user(first_name="Paul", last_name="Tchoumi", phone="677000001")
        self.client.force_login(self.user)
        self.url = reverse("accounts:profile")
        self.data = {"first_name": "Paulin", "last_name": "Tchoumi", "phone": "677000001", "language": "fr", "city": self.cat["city"].pk, "address": "Akwa", "notify_email": "on"}

    def test_profile_page_and_update(self):
        self.assertContains(self.client.get(self.url), "Mon compte")
        resp = self.client.post(self.url, self.data)
        self.assertRedirects(resp, self.url)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Paulin")
        profile = ClientProfile.objects.get(user=self.user)
        self.assertEqual((profile.city, profile.address, profile.notify_email, profile.notify_sms), (self.cat["city"], "Akwa", True, False))

    def test_language_cookie_set(self):
        resp = self.client.post(self.url, {**self.data, "language": "en"})
        self.assertEqual(resp.cookies["django_language"].value, "en")

    def test_email_cannot_be_changed(self):
        self.client.post(self.url, {**self.data, "email": "hack@x.cm"})
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.email, "hack@x.cm")

    def test_phone_must_be_unique_and_change_resets_verification(self):
        make_user(phone="677000002")
        resp = self.client.post(self.url, {**self.data, "phone": "677000002"})
        self.assertContains(resp, "déjà utilisé")
        User.objects.filter(pk=self.user.pk).update(phone_verified=True)
        self.client.post(self.url, {**self.data, "phone": "677000003"})
        self.user.refresh_from_db()
        self.assertEqual((self.user.phone, self.user.phone_verified), ("677000003", False))

    def test_avatar_upload_and_removal(self):
        self.client.post(self.url, {**self.data, "avatar": png()})
        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar)
        self.client.post(self.url, {**self.data, "remove_avatar": "on"})
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)

    def test_non_image_avatar_rejected(self):
        bad = SimpleUploadedFile("x.png", b"not an image", content_type="image/png")
        resp = self.client.post(self.url, {**self.data, "avatar": bad})
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)

    def test_provider_is_redirected_to_own_space(self):
        self.client.force_login(make_provider(self.cat).user)
        self.assertRedirects(self.client.get(self.url), reverse("dashboard_provider:home"), fetch_redirect_response=False)


class PasswordTests(TestCase):
    def setUp(self):
        self.user = make_user(password="AncienMdp-2026")
        self.client.force_login(self.user)
        self.url = reverse("accounts:password_change")

    def test_change_password_keeps_session(self):
        resp = self.client.post(self.url, {"old_password": "AncienMdp-2026", "new_password1": "NouveauMdp-2026!", "new_password2": "NouveauMdp-2026!"})
        self.assertRedirects(resp, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NouveauMdp-2026!"))
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 200)

    def test_wrong_old_password(self):
        resp = self.client.post(self.url, {"old_password": "faux", "new_password1": "NouveauMdp-2026!", "new_password2": "NouveauMdp-2026!"})
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("AncienMdp-2026"))

    def test_weak_password_rejected(self):
        self.client.post(self.url, {"old_password": "AncienMdp-2026", "new_password1": "12345678", "new_password2": "12345678"})
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("AncienMdp-2026"))


class DeleteAccountTests(TestCase):
    def setUp(self):
        self.cat = make_catalog()
        self.provider = make_provider(self.cat)
        self.user = make_user(first_name="Paul", last_name="Tchoumi", phone="677000009", password="Secret-2026!")
        self.client.force_login(self.user)
        self.url = reverse("accounts:delete")

    def test_wrong_password_keeps_account(self):
        resp = self.client.post(self.url, {"password": "mauvais"})
        self.assertContains(resp, "Mot de passe incorrect")
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_deletion_anonymises_and_keeps_reviews(self):
        Favorite.objects.create(user=self.user, provider=self.provider)
        req = make_request(self.user, self.provider, ServiceRequest.Status.DONE)
        Review.objects.create(request=req, client=self.user, provider=self.provider, rating=5, comment="Top")
        resp = self.client.post(self.url, {"password": "Secret-2026!"})
        self.assertRedirects(resp, reverse("core:home"), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertEqual((self.user.first_name, self.user.phone), ("", None))
        self.assertTrue(self.user.email.endswith("@kora.invalid"))
        self.assertFalse(self.user.has_usable_password())
        self.assertFalse(Favorite.objects.exists())
        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(self.user.public_name, "Client Kora")
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 302)  # déconnecté

    def test_cannot_log_in_afterwards(self):
        self.client.post(self.url, {"password": "Secret-2026!"})
        resp = self.client.post(reverse("accounts:login"), {"username": "677000009", "password": "Secret-2026!"})
        self.assertEqual(resp.status_code, 200)


class ClientHomeTests(TestCase):
    def setUp(self):
        self.cat = make_catalog()
        self.provider = make_provider(self.cat, business_name="Aqua Services")
        self.user = make_user(first_name="Paul")
        self.client.force_login(self.user)

    def test_home_summary(self):
        make_request(self.user, self.provider, ServiceRequest.Status.QUOTED)
        make_request(self.user, self.provider, ServiceRequest.Status.DONE)
        resp = self.client.get(reverse("core:client_home"))
        self.assertContains(resp, "Bonjour Paul")
        self.assertEqual(resp.context["open_count"], 1)
        self.assertEqual(len(resp.context["to_review"]), 1)
        self.assertContains(resp, "Donnez votre avis")

    def test_reviewed_request_no_longer_listed_for_review(self):
        req = make_request(self.user, self.provider, ServiceRequest.Status.DONE)
        Review.objects.create(request=req, client=self.user, provider=self.provider, rating=5)
        self.assertEqual(self.client.get(reverse("core:client_home")).context["to_review"], [])

    def test_suggestions_exclude_favorites_and_non_public(self):
        other = make_provider(self.cat, business_name="Autre Pro")
        make_provider(self.cat, ProviderProfile.Status.SUSPENDED, business_name="Suspendu")
        Favorite.objects.create(user=self.user, provider=self.provider)
        names = [p.business_name for p in self.client.get(reverse("core:client_home")).context["suggestions"]]
        self.assertEqual(names, ["Autre Pro"])

    def test_other_roles_are_redirected(self):
        self.client.force_login(self.provider.user)
        self.assertRedirects(self.client.get(reverse("core:client_home")), reverse("dashboard_provider:home"), fetch_redirect_response=False)

    def test_bottom_nav_adapts_by_role(self):
        resp = self.client.get(reverse("core:home"))
        self.assertContains(resp, reverse("favorites:list"))
        self.assertContains(resp, reverse("accounts:profile"))
        self.client.force_login(self.provider.user)
        resp = self.client.get(reverse("core:home"))
        self.assertNotContains(resp, f'href="{reverse("favorites:list")}"')
        self.assertNotContains(resp, f'href="{reverse("accounts:profile")}"')


from apps.providers.models import ProviderProfile  # noqa: E402
