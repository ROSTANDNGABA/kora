import json
import re

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.tests.factories import make_catalog, make_provider, make_request, make_user
from apps.providers.models import Availability, ProviderFieldValue, ProviderProfile, Service
from apps.catalog.models import CategoryField
from apps.requests_app.models import ServiceRequest
from apps.reviews.models import Review
from datetime import time

Status = ProviderProfile.Status


def add_review(provider, rating=5, comment="Très bien", status=Review.Status.VISIBLE, first="Aïcha", last="Ngono"):
    client = make_user(first_name=first, last_name=last)
    req = make_request(client, provider, ServiceRequest.Status.DONE)
    return Review.objects.create(request=req, client=client, provider=provider, rating=rating, comment=comment, status=status)


class DetailAccessTests(TestCase):
    def setUp(self):
        self.cat = make_catalog()
        self.provider = make_provider(self.cat, business_name="Aqua Services")

    def url(self, p=None):
        return (p or self.provider).get_absolute_url()

    def test_public_page_renders_for_anonymous(self):
        resp = self.client.get(self.url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Aqua Services")
        self.assertContains(resp, "Contacter sur WhatsApp")
        self.assertContains(resp, "Demander un devis")
        self.assertContains(resp, "index,follow")

    def test_non_public_statuses_are_404_for_visitors_and_clients(self):
        self.client.force_login(make_user())
        for st in (Status.PENDING, Status.SUSPENDED, Status.REJECTED):
            p = make_provider(self.cat, st)
            self.assertEqual(self.client.get(self.url(p)).status_code, 404, st)

    def test_inactive_user_account_hides_provider(self):
        self.provider.user.is_active = False
        self.provider.user.save()
        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_owner_and_admin_can_preview_pending_profile(self):
        p = make_provider(self.cat, Status.PENDING)
        self.client.force_login(p.user)
        resp = self.client.get(self.url(p))
        self.assertContains(resp, "Aperçu")
        self.assertContains(resp, "noindex")
        admin = make_user(role="ADMIN", email="a@t.cm")
        self.client.force_login(admin)
        self.assertEqual(self.client.get(self.url(p)).status_code, 200)

    def test_another_provider_cannot_preview(self):
        p = make_provider(self.cat, Status.PENDING)
        self.client.force_login(self.provider.user)
        self.assertEqual(self.client.get(self.url(p)).status_code, 404)

    def test_phone_is_never_displayed(self):
        self.provider.user.phone = "677112233"
        self.provider.user.save()
        self.assertNotContains(self.client.get(self.url()), "677112233")

    def test_contact_buttons_hidden_for_provider_accounts(self):
        other = make_provider(self.cat)
        self.client.force_login(other.user)
        resp = self.client.get(self.url())
        self.assertNotContains(resp, "Demander un devis")
        self.assertNotContains(resp, "Contacter sur WhatsApp")

    @override_settings(SUPPORT_WHATSAPP="")
    def test_whatsapp_link_goes_through_counter_not_raw_number(self):
        resp = self.client.get(self.url())
        self.assertContains(resp, reverse("providers:whatsapp", args=[self.provider.slug]))
        self.assertNotContains(resp, "wa.me/")

    def test_json_ld_is_valid_and_has_rating(self):
        add_review(self.provider)
        self.provider.refresh_from_db()
        html = self.client.get(self.url()).content.decode()
        raw = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1)
        data = json.loads(raw)
        self.assertEqual(data["@type"], "LocalBusiness")
        self.assertEqual(data["aggregateRating"]["reviewCount"], 1)

    def test_json_ld_cannot_break_out_of_script_tag(self):
        self.provider.description = "</script><script>alert(1)</script>"
        self.provider.save()
        html = self.client.get(self.url()).content.decode()
        self.assertNotIn("</script><script>alert(1)", html)

    def test_description_html_is_escaped(self):
        self.provider.description = "<b>gras</b><img src=x onerror=alert(1)>"
        self.provider.save()
        html = self.client.get(self.url()).content.decode()
        self.assertNotIn("<img src=x", html)

    def test_unknown_slug_is_404(self):
        self.assertEqual(self.client.get("/artisans/nexiste-pas/").status_code, 404)


class DetailContentTests(TestCase):
    def setUp(self):
        self.cat = make_catalog()
        self.provider = make_provider(self.cat, business_name="Aqua Services", description="Dépannage rapide")

    def get(self):
        return self.client.get(self.provider.get_absolute_url())

    def test_services_with_price_types(self):
        Service.objects.create(provider=self.provider, title="Fuite", price_type="FIXED", amount=15000, duration_minutes=90)
        Service.objects.create(provider=self.provider, title="Installation", price_type="FROM", amount=40000)
        Service.objects.create(provider=self.provider, title="Chantier", price_type="QUOTE")
        Service.objects.create(provider=self.provider, title="Caché", amount=1, is_active=False)
        resp = self.get()
        self.assertContains(resp, "15 000 FCFA")
        self.assertContains(resp, "1 h 30")
        self.assertContains(resp, "dès")
        self.assertContains(resp, "Sur devis")
        self.assertNotContains(resp, "Caché")

    def test_specific_fields_hide_empty_and_false(self):
        urgence = self.cat["plomberie"].fields.get(key="urgence")
        extra = CategoryField.objects.create(category=self.cat["plomberie"], label="Matériel", key="materiel", field_type="TEXT")
        vide = CategoryField.objects.create(category=self.cat["plomberie"], label="Marque", key="marque", field_type="TEXT")
        ProviderFieldValue.objects.create(provider=self.provider, field=urgence, value="true")
        ProviderFieldValue.objects.create(provider=self.provider, field=extra, value="Chalumeau")
        ProviderFieldValue.objects.create(provider=self.provider, field=vide, value="  ")
        resp = self.get()
        self.assertContains(resp, "Urgence 24/7")
        self.assertContains(resp, "Chalumeau")
        self.assertNotContains(resp, "Marque")

    def test_hours_listed(self):
        Availability.objects.create(provider=self.provider, weekday=0, opens_at=time(8), closes_at=time(18))
        Availability.objects.create(provider=self.provider, weekday=6, is_closed=True)
        resp = self.get()
        self.assertContains(resp, "08:00 – 18:00")
        self.assertContains(resp, "Fermé")

    def test_unavailable_badge(self):
        self.provider.is_unavailable = True
        self.provider.save()
        self.assertContains(self.get(), "Indisponible pour le moment")

    def test_reviews_exclude_hidden_and_mask_last_name(self):
        add_review(self.provider, 5, "Excellent travail")
        add_review(self.provider, 1, "Avis modéré", status=Review.Status.HIDDEN)
        self.provider.refresh_from_db()
        resp = self.get()
        self.assertContains(resp, "Excellent travail")
        self.assertNotContains(resp, "Avis modéré")
        self.assertContains(resp, "Aïcha N.")
        self.assertNotContains(resp, "Ngono")
        self.assertEqual(resp.context["reviews_total"], 1)

    def test_rating_distribution(self):
        for r in (5, 5, 4, 1):
            add_review(self.provider, r)
        bars = {b["stars"]: b for b in self.get().context["rating_bars"]}
        self.assertEqual(bars[5]["count"], 2)
        self.assertEqual(bars[5]["pct"], 50)
        self.assertEqual(bars[3]["count"], 0)

    def test_no_python_object_leaks_into_stars(self):
        add_review(self.provider)
        self.provider.refresh_from_db()
        self.assertNotContains(self.get(), "&lt;Review")

    def test_provider_reply_is_shown(self):
        review = add_review(self.provider)
        review.provider_reply = "Merci beaucoup !"
        review.save()
        self.assertContains(self.get(), "Merci beaucoup !")

    def test_reviews_pagination_fragment(self):
        for _ in range(8):
            add_review(self.provider)
        resp = self.get()
        self.assertEqual(len(resp.context["review_items"]), 6)
        self.assertEqual(resp.context["next_reviews_page"], 2)
        more = self.client.get(reverse("providers:reviews", args=[self.provider.slug]), {"page": 2}, HTTP_HX_REQUEST="true")
        self.assertEqual(len(more.context["review_items"]), 2)
        self.assertNotContains(more, "Voir plus d'avis")
        self.assertEqual(self.client.get(reverse("providers:reviews", args=[self.provider.slug]), {"page": "x"}).status_code, 200)

    def test_reviews_fragment_404_for_non_public(self):
        p = make_provider(self.cat, Status.SUSPENDED)
        self.assertEqual(self.client.get(reverse("providers:reviews", args=[p.slug])).status_code, 404)

    def test_similar_providers_same_category_and_city_exclude_self(self):
        other = make_provider(self.cat, business_name="Voisin Pro")
        make_provider(self.cat, Status.PENDING, business_name="Pas Visible")
        resp = self.get()
        self.assertEqual(resp.context["similar"], [other])
        self.assertNotContains(resp, "Pas Visible")

    def test_report_links_by_role(self):
        self.assertContains(self.get(), "Connectez-vous pour signaler")
        self.client.force_login(make_user())
        self.assertContains(self.get(), reverse("reviews:report", args=["provider", self.provider.pk]))
        self.client.force_login(self.provider.user)
        self.assertNotContains(self.get(), "Signaler ce profil")

    def test_messaging_button_present(self):
        self.assertContains(self.get(), "Envoyer un message")


class CountersTests(TestCase):
    def setUp(self):
        self.cat = make_catalog()
        self.provider = make_provider(self.cat)

    def reload(self):
        self.provider.refresh_from_db()
        return self.provider

    def test_views_counted_once_per_session(self):
        for _ in range(3):
            self.client.get(self.provider.get_absolute_url())
        self.assertEqual(self.reload().views_count, 1)

    def test_other_session_counts_again(self):
        self.client.get(self.provider.get_absolute_url())
        from django.test import Client

        Client().get(self.provider.get_absolute_url())
        self.assertEqual(self.reload().views_count, 2)

    def test_owner_views_not_counted(self):
        self.client.force_login(self.provider.user)
        self.client.get(self.provider.get_absolute_url())
        self.assertEqual(self.reload().views_count, 0)

    def test_preview_of_non_public_not_counted(self):
        p = make_provider(self.cat, Status.PENDING)
        admin = make_user(role="ADMIN", email="adm@t.cm")
        self.client.force_login(admin)
        self.client.get(p.get_absolute_url())
        p.refresh_from_db()
        self.assertEqual(p.views_count, 0)

    def test_whatsapp_redirects_with_prefilled_message_and_counts_once(self):
        url = reverse("providers:whatsapp", args=[self.provider.slug])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp["Location"].startswith("https://wa.me/237699000000?text="))
        self.assertIn("Kora", resp["Location"])
        self.client.get(url)
        self.assertEqual(self.reload().whatsapp_clicks, 1)

    def test_whatsapp_number_normalisation(self):
        self.provider.whatsapp = "+237 6 99 00 00 00"
        self.provider.save()
        resp = self.client.get(reverse("providers:whatsapp", args=[self.provider.slug]))
        self.assertIn("wa.me/237699000000", resp["Location"])

    def test_whatsapp_404_for_non_public_provider_and_no_count(self):
        p = make_provider(self.cat, Status.SUSPENDED)
        self.assertEqual(self.client.get(reverse("providers:whatsapp", args=[p.slug])).status_code, 404)
        p.refresh_from_db()
        self.assertEqual(p.whatsapp_clicks, 0)

    def test_whatsapp_requires_get_only_through_redirect_not_indexed(self):
        resp = self.client.get(reverse("providers:whatsapp", args=[self.provider.slug]))
        self.assertEqual(resp["X-Robots-Tag"], "noindex")
