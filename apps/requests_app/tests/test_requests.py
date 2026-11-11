import io
from datetime import timedelta

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.core.tests.factories import make_catalog, make_provider, make_quote, make_request, make_user
from apps.notifications.models import Notification
from apps.providers.models import ProviderProfile, Service
from apps.requests_app import services
from apps.requests_app.models import Quote, ServiceRequest

S = ServiceRequest.Status
Status = ProviderProfile.Status


def image(name="photo.png", size=(20, 20)):
    buf = io.BytesIO()
    Image.new("RGB", size, "orange").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


class CreateRequestTests(TestCase):
    def setUp(self):
        cache.clear()
        self.cat = make_catalog()
        self.provider = make_provider(self.cat, business_name="Aqua Services")
        self.user = make_user(first_name="Paul", last_name="Tchoumi")
        self.client.force_login(self.user)
        self.url = reverse("requests_app:create", args=[self.provider.slug])
        self.data = {"description": "Une fuite sous mon évier depuis hier soir", "city": self.cat["city"].pk}

    def test_form_renders_with_provider_city_prefilled(self):
        resp = self.client.get(self.url)
        self.assertContains(resp, "Aqua Services")
        self.assertEqual(resp.context["form"].initial["city"], self.cat["city"])

    def test_service_query_prefills_description(self):
        s = Service.objects.create(provider=self.provider, title="Réparation de fuite", amount=10000)
        resp = self.client.get(self.url, {"service": s.pk})
        self.assertEqual(resp.context["form"].initial["description"], "Réparation de fuite : ")

    def test_valid_request_is_created_and_provider_notified(self):
        resp = self.client.post(self.url, self.data)
        req = ServiceRequest.objects.get()
        self.assertRedirects(resp, reverse("requests_app:detail", args=[req.pk]))
        self.assertEqual((req.client, req.provider, req.status), (self.user, self.provider, S.SENT))
        n = Notification.objects.get(user=self.provider.user)
        self.assertEqual(n.type, "REQUEST")
        self.assertIn("Paul T.", n.title)

    def test_photos_are_saved(self):
        self.client.post(self.url, {**self.data, "photos": [image("a.png"), image("b.png")]})
        self.assertEqual(ServiceRequest.objects.get().photos.count(), 2)

    def test_too_many_photos_rejected(self):
        resp = self.client.post(self.url, {**self.data, "photos": [image(f"{i}.png") for i in range(6)]})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(ServiceRequest.objects.exists())
        self.assertContains(resp, "maximum 5 photos")

    def test_non_image_rejected(self):
        fake = SimpleUploadedFile("virus.png", b"MZ not an image", content_type="image/png")
        resp = self.client.post(self.url, {**self.data, "photos": [fake]})
        self.assertFalse(ServiceRequest.objects.exists())
        self.assertEqual(resp.status_code, 200)

    def test_oversized_photo_rejected(self):
        from unittest import mock

        with mock.patch("apps.requests_app.forms.upload_limit_bytes", return_value=10):
            resp = self.client.post(self.url, {**self.data, "photos": [image()]})
        self.assertFalse(ServiceRequest.objects.exists())
        self.assertContains(resp, "dépasse")

    def test_validation_errors(self):
        resp = self.client.post(self.url, {**self.data, "description": "court"})
        self.assertContains(resp, "15 caractères minimum")
        yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
        resp = self.client.post(self.url, {**self.data, "desired_date": yesterday})
        self.assertContains(resp, "dans le passé")
        self.assertFalse(ServiceRequest.objects.exists())

    def test_non_public_provider_404(self):
        p = make_provider(self.cat, Status.SUSPENDED)
        self.assertEqual(self.client.get(reverse("requests_app:create", args=[p.slug])).status_code, 404)

    def test_anonymous_goes_to_login_and_provider_is_redirected(self):
        self.client.logout()
        self.assertIn(reverse("accounts:login"), self.client.get(self.url)["Location"])
        self.client.force_login(make_provider(self.cat).user)
        self.assertRedirects(self.client.get(self.url), reverse("dashboard_provider:home"), fetch_redirect_response=False)
        self.assertEqual(self.client.post(self.url, self.data).status_code, 302)
        self.assertFalse(ServiceRequest.objects.exists())

    def test_daily_limit(self):
        for _ in range(10):
            self.client.post(self.url, self.data)
        resp = self.client.post(self.url, self.data)
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(ServiceRequest.objects.count(), 10)


class MyRequestsTests(TestCase):
    def setUp(self):
        self.cat = make_catalog()
        self.provider = make_provider(self.cat, business_name="Aqua Services")
        self.user = make_user()
        self.client.force_login(self.user)

    def test_list_filters_and_counts(self):
        make_request(self.user, self.provider, S.SENT)
        make_request(self.user, self.provider, S.DONE)
        make_request(self.user, self.provider, S.CANCELLED)
        make_request(self.user, self.provider, S.REFUSED)
        make_request(make_user(), self.provider, S.SENT)  # d'un autre client
        url = reverse("requests_app:list")
        resp = self.client.get(url)
        self.assertEqual(resp.context["counts"], {"toutes": 4, "en-cours": 1, "terminees": 1, "fermees": 2})
        self.assertEqual(len(self.client.get(url, {"statut": "fermees"}).context["requests"]), 2)
        self.assertEqual(len(self.client.get(url, {"statut": "bidon"}).context["requests"]), 4)

    def test_review_button_only_for_unreviewed_done(self):
        done = make_request(self.user, self.provider, S.DONE)
        resp = self.client.get(reverse("requests_app:list"))
        self.assertContains(resp, reverse("reviews:create", args=[done.pk]))

    def test_detail_is_private_to_owner(self):
        req = make_request(self.user, self.provider)
        self.assertEqual(self.client.get(reverse("requests_app:detail", args=[req.pk])).status_code, 200)
        self.client.force_login(make_user())
        self.assertEqual(self.client.get(reverse("requests_app:detail", args=[req.pk])).status_code, 404)
        self.client.force_login(self.provider.user)  # le prestataire passe par son propre espace
        self.assertEqual(self.client.get(reverse("requests_app:detail", args=[req.pk])).status_code, 302)

    def test_detail_shows_every_status(self):
        for st in S.values:
            req = make_request(self.user, self.provider, st)
            self.assertEqual(self.client.get(reverse("requests_app:detail", args=[req.pk])).status_code, 200, st)

    def test_pages_require_login(self):
        self.client.logout()
        for name in ("requests_app:list", "core:client_home", "favorites:list", "accounts:profile"):
            self.assertIn(reverse("accounts:login"), self.client.get(reverse(name))["Location"], name)


class StatusFlowTests(TestCase):
    def setUp(self):
        self.cat = make_catalog()
        self.provider = make_provider(self.cat)
        self.user = make_user()
        self.client.force_login(self.user)

    def post(self, name, pk):
        return self.client.post(reverse(name, args=[pk]), follow=True)

    def test_full_flow_request_quote_accept_progress_done(self):
        req = make_request(self.user, self.provider)
        pro = self.provider.user
        services.change_status(req, S.VIEWED, pro)
        quote = make_quote(req, 25000, delay_days=3)
        services.change_status(req, S.QUOTED, pro)
        self.assertTrue(Notification.objects.filter(user=self.user, title="Vous avez reçu un devis").exists())
        self.post("requests_app:quote_accept", quote.pk)
        req.refresh_from_db(), quote.refresh_from_db()
        self.assertEqual((req.status, quote.status), (S.ACCEPTED, Quote.Status.ACCEPTED))
        self.assertTrue(Notification.objects.filter(user=pro, title="Devis accepté").exists())
        services.change_status(req, S.IN_PROGRESS, pro)
        done = services.change_status(req, S.DONE, pro)
        self.assertIsNotNone(done.completed_at)
        self.assertTrue(Notification.objects.filter(user=self.user, title="Prestation terminée").exists())

    def test_every_status_change_notifies_the_other_party(self):
        req = make_request(self.user, self.provider)
        services.change_status(req, S.VIEWED, self.provider.user)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)
        services.cancel_by_client(req, self.user)
        self.assertEqual(Notification.objects.filter(user=self.provider.user).count(), 1)

    def test_invalid_transitions_are_rejected(self):
        req = make_request(self.user, self.provider, S.DONE)
        for target in (S.SENT, S.CANCELLED, S.IN_PROGRESS):
            with self.assertRaises(services.InvalidTransition):
                services.change_status(req, target, self.provider.user)
        cancelled = make_request(self.user, self.provider, S.CANCELLED)
        with self.assertRaises(services.InvalidTransition):
            services.change_status(cancelled, S.VIEWED, self.provider.user)

    def test_cannot_skip_to_done(self):
        req = make_request(self.user, self.provider, S.ACCEPTED)
        with self.assertRaises(services.InvalidTransition):
            services.change_status(req, S.DONE, self.provider.user)

    def test_refusal_stores_reason(self):
        req = make_request(self.user, self.provider)
        services.change_status(req, S.REFUSED, self.provider.user, reason="Complet jusqu'en décembre")
        req.refresh_from_db()
        self.assertEqual(req.refusal_reason, "Complet jusqu'en décembre")
        self.assertIn("Complet", Notification.objects.get(user=self.user).body)

    def test_client_cancel_allowed_states(self):
        for st in (S.SENT, S.VIEWED, S.QUOTED, S.ACCEPTED):
            req = make_request(self.user, self.provider, st)
            self.post("requests_app:cancel", req.pk)
            req.refresh_from_db()
            self.assertEqual(req.status, S.CANCELLED, st)

    def test_client_cannot_cancel_in_progress_or_finished(self):
        for st in (S.IN_PROGRESS, S.DONE, S.REFUSED):
            req = make_request(self.user, self.provider, st)
            self.post("requests_app:cancel", req.pk)
            req.refresh_from_db()
            self.assertEqual(req.status, st, st)

    def test_cancel_is_post_only_and_owner_only(self):
        req = make_request(self.user, self.provider)
        self.assertEqual(self.client.get(reverse("requests_app:cancel", args=[req.pk])).status_code, 405)
        self.client.force_login(make_user())
        self.assertEqual(self.client.post(reverse("requests_app:cancel", args=[req.pk])).status_code, 404)
        req.refresh_from_db()
        self.assertEqual(req.status, S.SENT)

    def test_decline_only_quote_reopens_request_for_a_new_quote(self):
        req = make_request(self.user, self.provider, S.QUOTED)
        quote = make_quote(req)
        self.post("requests_app:quote_decline", quote.pk)
        req.refresh_from_db(), quote.refresh_from_db()
        self.assertEqual((req.status, quote.status), (S.VIEWED, Quote.Status.DECLINED))

    def test_decline_one_of_two_quotes_keeps_request_quoted(self):
        req = make_request(self.user, self.provider, S.QUOTED)
        q1, q2 = make_quote(req, 10000), make_quote(req, 20000)
        self.post("requests_app:quote_decline", q1.pk)
        req.refresh_from_db()
        self.assertEqual(req.status, S.QUOTED)

    def test_accepting_one_quote_declines_the_others(self):
        req = make_request(self.user, self.provider, S.QUOTED)
        q1, q2 = make_quote(req, 10000), make_quote(req, 20000)
        self.post("requests_app:quote_accept", q2.pk)
        q1.refresh_from_db(), q2.refresh_from_db()
        self.assertEqual((q1.status, q2.status), (Quote.Status.DECLINED, Quote.Status.ACCEPTED))

    def test_expired_quote_cannot_be_accepted(self):
        req = make_request(self.user, self.provider, S.QUOTED)
        quote = make_quote(req, valid_until=timezone.localdate() - timedelta(days=1))
        self.post("requests_app:quote_accept", quote.pk)
        req.refresh_from_db()
        self.assertEqual(req.status, S.QUOTED)

    def test_accepting_twice_is_harmless(self):
        req = make_request(self.user, self.provider, S.QUOTED)
        quote = make_quote(req)
        self.post("requests_app:quote_accept", quote.pk)
        self.post("requests_app:quote_accept", quote.pk)
        self.assertEqual(Notification.objects.filter(user=self.provider.user, title="Devis accepté").count(), 1)

    def test_other_clients_quote_is_404(self):
        req = make_request(make_user(), self.provider, S.QUOTED)
        quote = make_quote(req)
        self.assertEqual(self.client.post(reverse("requests_app:quote_accept", args=[quote.pk])).status_code, 404)
        req.refresh_from_db()
        self.assertEqual(req.status, S.QUOTED)

    def test_detail_offers_actions_matching_status(self):
        req = make_request(self.user, self.provider, S.QUOTED)
        make_quote(req)
        resp = self.client.get(reverse("requests_app:detail", args=[req.pk]))
        self.assertContains(resp, "Accepter ce devis")
        self.assertContains(resp, "Annuler la demande")
        req2 = make_request(self.user, self.provider, S.IN_PROGRESS)
        self.assertNotContains(self.client.get(reverse("requests_app:detail", args=[req2.pk])), "Annuler la demande")
