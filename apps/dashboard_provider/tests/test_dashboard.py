import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.accounts.models import User
from apps.core.tests.factories import make_catalog, make_provider, make_quote, make_request, make_user
from apps.core.site_settings import clear_cache
from apps.notifications.models import Notification
from apps.providers.models import PortfolioMedia, ProviderProfile, Service, Verification
from apps.requests_app.models import ServiceRequest

S = ServiceRequest.Status
TMP = tempfile.mkdtemp()


def png(size=(200, 120), name="p.png"):
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 80, 20)).save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=TMP)
class DashboardBase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        clear_cache()
        self.cat = make_catalog()
        self.profile = make_provider(self.cat)
        self.user = self.profile.user
        self.client_user = make_user()
        self.client.force_login(self.user)


class PagesTests(DashboardBase):
    def test_all_pages_render(self):
        req = make_request(self.client_user, self.profile)
        names = ["home", "profile", "portfolio", "services", "service_new", "availability", "requests", "reviews", "stats", "verification", "settings"]
        for name in names:
            with self.subTest(name):
                self.assertEqual(self.client.get(reverse(f"dashboard_provider:{name}")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard_provider:request_detail", args=[req.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("messaging:inbox")).status_code, 200)
        self.assertEqual(self.client.get(reverse("notifications:list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("accounts:password_change")).status_code, 200)

    def test_stats_periods(self):
        for p in (7, 30, 90, "abc", 5):
            self.assertEqual(self.client.get(reverse("dashboard_provider:stats"), {"periode": p}).status_code, 200)

    def test_role_isolation(self):
        self.client.force_login(self.client_user)
        r = self.client.get(reverse("dashboard_provider:home"))
        self.assertIn(r.status_code, (302, 403))
        self.client.logout()
        self.assertEqual(self.client.get(reverse("dashboard_provider:home")).status_code, 302)

    def test_sidebar_links_are_live(self):
        html = self.client.get(reverse("dashboard_provider:home")).content.decode()
        for name in ("profile", "portfolio", "services", "availability", "requests", "reviews", "stats", "verification", "settings"):
            self.assertIn(reverse(f"dashboard_provider:{name}"), html)
        self.assertIn(reverse("messaging:inbox"), html)


class ProfileTests(DashboardBase):
    def data(self, **kw):
        d = {"business_name": "Aqua Pro", "activity_type": "FREELANCE", "description": "Plombier depuis dix ans à Douala", "city": self.cat["city"].pk, "whatsapp": "699111222"}
        d.update(kw)
        return d

    def test_update_and_dynamic_field(self):
        field = self.cat["plomberie"].fields.get(key="urgence")
        r = self.client.post(reverse("dashboard_provider:profile"), self.data(**{f"extra_{field.pk}": "on"}))
        self.assertEqual(r.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.business_name, "Aqua Pro")
        self.assertTrue(self.profile.field_values.filter(field=field).exists())

    def test_category_change_requires_validation(self):
        r = self.client.post(reverse("dashboard_provider:profile"), self.data(new_category=self.cat["couture"].pk))
        self.assertEqual(r.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.category, self.cat["plomberie"])
        self.assertEqual(self.profile.pending_category, self.cat["couture"])

    def test_cancel_category_change(self):
        self.profile.pending_category = self.cat["couture"]
        self.profile.save()
        self.client.post(reverse("dashboard_provider:profile"), self.data(cancel_category_change="on"))
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.pending_category)

    def test_invalid_whatsapp_rejected(self):
        r = self.client.post(reverse("dashboard_provider:profile"), self.data(whatsapp="abc"))
        self.assertEqual(r.status_code, 200)

    def test_non_image_logo_rejected(self):
        bad = SimpleUploadedFile("x.png", b"not an image", content_type="image/png")
        r = self.client.post(reverse("dashboard_provider:profile"), {**self.data(), "logo": bad})
        self.assertEqual(r.status_code, 200)


class PortfolioTests(DashboardBase):
    def test_upload_compresses(self):
        r = self.client.post(reverse("dashboard_provider:portfolio"), {"images": [png((3000, 2000), "a.png"), png(name="b.png")]})
        self.assertEqual(r.status_code, 302)
        items = list(self.profile.portfolio.all())
        self.assertEqual(len(items), 2)
        self.assertLessEqual(max(Image.open(items[0].image.path).size), 1600)

    def test_limit_enforced(self):
        from apps.core.models import SiteSettings

        SiteSettings.objects.update_or_create(pk=1, defaults={"portfolio_max_items": 1})
        clear_cache()
        r = self.client.post(reverse("dashboard_provider:portfolio"), {"images": [png(name="a.png"), png(name="b.png")]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.profile.portfolio.count(), 0)

    def test_fake_image_rejected(self):
        r = self.client.post(reverse("dashboard_provider:portfolio"), {"images": [SimpleUploadedFile("a.png", b"<script>", content_type="image/png")]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.profile.portfolio.count(), 0)

    def test_caption_move_delete_and_ownership(self):
        self.client.post(reverse("dashboard_provider:portfolio"), {"images": [png(name="a.png"), png(name="b.png")]})
        first, second = self.profile.portfolio.all()
        self.client.post(reverse("dashboard_provider:portfolio_caption", args=[first.pk]), {"caption": "Salle de bain"})
        first.refresh_from_db()
        self.assertEqual(first.caption, "Salle de bain")
        self.client.post(reverse("dashboard_provider:portfolio_move", args=[first.pk, "bas"]))
        self.assertEqual(list(self.profile.portfolio.values_list("pk", flat=True)), [second.pk, first.pk])
        other = make_provider(self.cat)
        foreign = PortfolioMedia.objects.create(provider=other, image="x.jpg", order=0)
        self.assertEqual(self.client.post(reverse("dashboard_provider:portfolio_delete", args=[foreign.pk])).status_code, 404)
        self.client.post(reverse("dashboard_provider:portfolio_delete", args=[first.pk]))
        self.assertEqual(self.profile.portfolio.count(), 1)

    def test_get_not_allowed_on_delete(self):
        m = PortfolioMedia.objects.create(provider=self.profile, image="x.jpg", order=0)
        self.assertEqual(self.client.get(reverse("dashboard_provider:portfolio_delete", args=[m.pk])).status_code, 405)


class ServiceTests(DashboardBase):
    def test_crud(self):
        r = self.client.post(reverse("dashboard_provider:service_new"), {"title": "Réparation fuite", "price_type": "FIXED", "amount": 10000, "is_active": "on"})
        self.assertEqual(r.status_code, 302)
        s = Service.objects.get(provider=self.profile)
        self.client.post(reverse("dashboard_provider:service_edit", args=[s.pk]), {"title": "Fuite", "price_type": "QUOTE", "is_active": "on"})
        s.refresh_from_db()
        self.assertEqual((s.title, s.amount), ("Fuite", None))
        self.client.post(reverse("dashboard_provider:service_toggle", args=[s.pk]))
        s.refresh_from_db()
        self.assertFalse(s.is_active)
        self.client.post(reverse("dashboard_provider:service_delete", args=[s.pk]))
        self.assertFalse(Service.objects.exists())

    def test_fixed_price_needs_amount(self):
        r = self.client.post(reverse("dashboard_provider:service_new"), {"title": "X", "price_type": "FIXED"})
        self.assertEqual(r.status_code, 200)

    def test_cannot_touch_other_provider_service(self):
        other = make_provider(self.cat)
        s = Service.objects.create(provider=other, title="Autre", price_type="QUOTE")
        self.assertEqual(self.client.get(reverse("dashboard_provider:service_edit", args=[s.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("dashboard_provider:service_delete", args=[s.pk])).status_code, 404)


class AvailabilityTests(DashboardBase):
    def test_save_hours_and_vacation(self):
        data = {"is_unavailable": "on", "home_service": "on", "closed_5": "on", "closed_6": "on"}
        for n in range(0, 5):
            data[f"open_{n}"], data[f"close_{n}"] = "08:00", "17:00"
        r = self.client.post(reverse("dashboard_provider:availability"), data)
        self.assertEqual(r.status_code, 302)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_unavailable)
        self.assertTrue(self.profile.availabilities.filter(weekday=0).exists())

    def test_close_before_open_rejected(self):
        r = self.client.post(reverse("dashboard_provider:availability"), {"open_0": "18:00", "close_0": "08:00", **{f"closed_{n}": "on" for n in range(1, 7)}})
        self.assertEqual(r.status_code, 200)


class RequestFlowTests(DashboardBase):
    def test_detail_marks_viewed_and_notifies(self):
        req = make_request(self.client_user, self.profile)
        self.client.get(reverse("dashboard_provider:request_detail", args=[req.pk]))
        req.refresh_from_db()
        self.assertEqual(req.status, S.VIEWED)
        self.assertTrue(Notification.objects.filter(user=self.client_user).exists())

    def test_accept_start_finish(self):
        req = make_request(self.client_user, self.profile)
        for name, expected in (("request_accept", S.ACCEPTED), ("request_start", S.IN_PROGRESS), ("request_finish", S.DONE)):
            self.client.post(reverse(f"dashboard_provider:{name}", args=[req.pk]))
            req.refresh_from_db()
            self.assertEqual(req.status, expected)

    def test_refuse_with_reason(self):
        req = make_request(self.client_user, self.profile)
        self.client.post(reverse("dashboard_provider:request_refuse", args=[req.pk]), {"reason": "Planning complet"})
        req.refresh_from_db()
        self.assertEqual((req.status, req.refusal_reason), (S.REFUSED, "Planning complet"))

    def test_send_quote(self):
        req = make_request(self.client_user, self.profile)
        r = self.client.post(reverse("dashboard_provider:request_quote", args=[req.pk]), {"amount": 25000, "delay_days": 2, "message": "OK"})
        self.assertEqual(r.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, S.QUOTED)
        self.assertEqual(req.quotes.get().amount, 25000)

    def test_invalid_quote_rerenders(self):
        req = make_request(self.client_user, self.profile)
        r = self.client.post(reverse("dashboard_provider:request_quote", args=[req.pk]), {"amount": 0, "delay_days": 2})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(req.quotes.exists())

    def test_invalid_transition_is_harmless(self):
        req = make_request(self.client_user, self.profile, status=S.DONE)
        self.client.post(reverse("dashboard_provider:request_start", args=[req.pk]))
        req.refresh_from_db()
        self.assertEqual(req.status, S.DONE)

    def test_cannot_access_other_provider_request(self):
        other = make_provider(self.cat)
        req = make_request(self.client_user, other)
        self.assertEqual(self.client.get(reverse("dashboard_provider:request_detail", args=[req.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("dashboard_provider:request_accept", args=[req.pk])).status_code, 404)

    def test_pending_provider_cannot_act(self):
        self.profile.status = ProviderProfile.Status.PENDING
        self.profile.save()
        req = make_request(self.client_user, self.profile)
        self.client.post(reverse("dashboard_provider:request_accept", args=[req.pk]))
        req.refresh_from_db()
        self.assertEqual(req.status, S.SENT)

    def test_filters(self):
        make_request(self.client_user, self.profile)
        make_request(self.client_user, self.profile, status=S.DONE)
        r = self.client.get(reverse("dashboard_provider:requests"), {"statut": "terminees"})
        self.assertEqual(len(r.context["page_obj"].object_list), 1)
        r = self.client.get(reverse("dashboard_provider:requests"), {"statut": "bidon"})
        self.assertEqual(len(r.context["page_obj"].object_list), 2)


class ReviewVerificationSettingsTests(DashboardBase):
    def test_reply_to_review(self):
        from apps.reviews.models import Review

        req = make_request(self.client_user, self.profile, status=S.DONE)
        rev = Review.objects.create(request=req, client=self.client_user, provider=self.profile, rating=5, comment="Top")
        self.client.post(reverse("dashboard_provider:review_reply", args=[rev.pk]), {"reply": "Merci !"})
        rev.refresh_from_db()
        self.assertEqual(rev.provider_reply, "Merci !")
        self.assertIsNotNone(rev.replied_at)

    def test_cannot_reply_to_other_provider_review(self):
        from apps.reviews.models import Review

        other = make_provider(self.cat)
        req = make_request(self.client_user, other, status=S.DONE)
        rev = Review.objects.create(request=req, client=self.client_user, provider=other, rating=3)
        self.assertEqual(self.client.post(reverse("dashboard_provider:review_reply", args=[rev.pk]), {"reply": "x"}).status_code, 404)

    def pdf(self, name="cni.pdf"):
        return SimpleUploadedFile(name, b"%PDF-1.4 test", content_type="application/pdf")

    def test_verification_upload(self):
        r = self.client.post(reverse("dashboard_provider:verification"), {"id_document": self.pdf()})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Verification.objects.get().status, "PENDING")
        # second dossier refusé tant que le premier est en cours
        self.client.post(reverse("dashboard_provider:verification"), {"id_document": self.pdf("b.pdf")})
        self.assertEqual(Verification.objects.count(), 1)

    def test_verification_rejects_disguised_file(self):
        bad = SimpleUploadedFile("cni.pdf", b"MZ\x90 exe", content_type="application/pdf")
        r = self.client.post(reverse("dashboard_provider:verification"), {"id_document": bad})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Verification.objects.exists())

    def test_settings_update(self):
        r = self.client.post(reverse("dashboard_provider:settings"), {"first_name": "Paul", "last_name": "Mbarga", "language": "fr"})
        self.assertEqual(r.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Paul")

    def test_password_change_redirects_to_settings(self):
        r = self.client.post(reverse("accounts:password_change"), {"old_password": "pass12345", "new_password1": "Nouveau-mdp-2026", "new_password2": "Nouveau-mdp-2026"})
        self.assertRedirects(r, reverse("dashboard_provider:settings"), fetch_redirect_response=False)
