from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.catalog.models import Category, City
from apps.cms.models import FAQ, StaticPage
from apps.core.tests.factories import make_catalog, make_provider, make_user
from apps.providers.models import ProviderProfile
from apps.requests_app.models import ServiceRequest
from apps.reviews.models import Review

Status = ProviderProfile.Status


def make_review(provider, rating=5, comment="Très bon travail", status=Review.Status.VISIBLE, first="Aïcha", last="Ngono"):
    client = make_user(first_name=first, last_name=last)
    req = ServiceRequest.objects.create(
        client=client, provider=provider, description="x", city=provider.city, status=ServiceRequest.Status.DONE
    )
    return Review.objects.create(request=req, client=client, provider=provider, rating=rating, comment=comment, status=status)


class LandingTests(TestCase):
    def setUp(self):
        self.cat = make_catalog()

    def get(self):
        return self.client.get(reverse("core:home"))

    def test_renders_for_anonymous_with_main_sections(self):
        resp = self.get()
        self.assertEqual(resp.status_code, 200)
        for text in ("Comment ça marche", "Villes disponibles", "Rejoignez la communauté Kora", "Pour les clients", "Pour les artisans"):
            self.assertContains(resp, text)
        self.assertContains(resp, 'action="/recherche/"')

    def test_category_cards_link_to_category_pages(self):
        resp = self.get()
        for c in Category.objects.all():
            self.assertContains(resp, f'href="{c.get_absolute_url()}"')

    def test_counters_come_from_database_and_only_count_public_data(self):
        make_provider(self.cat, Status.ACTIVE)
        make_provider(self.cat, Status.ACTIVE)
        make_provider(self.cat, Status.PENDING)
        make_provider(self.cat, Status.SUSPENDED)
        ctx = self.get().context["stats"]
        self.assertEqual(ctx["providers"], 2)
        self.assertEqual(ctx["cities"], 1)
        self.assertEqual(ctx["clients"], 0)  # les comptes prestataires ne sont pas des clients
        make_user()
        self.assertEqual(self.get().context["stats"]["clients"], 1)

    def test_reviews_counter_excludes_hidden(self):
        p = make_provider(self.cat)
        make_review(p, 5)
        make_review(p, 4, status=Review.Status.HIDDEN)
        self.assertEqual(self.get().context["stats"]["reviews"], 1)

    def test_featured_only_active_and_flagged(self):
        shown = make_provider(self.cat, Status.ACTIVE, is_featured=True, business_name="Visible Pro")
        make_provider(self.cat, Status.ACTIVE, is_featured=False, business_name="Pas Mis En Avant")
        make_provider(self.cat, Status.PENDING, is_featured=True, business_name="En Attente Pro")
        make_provider(self.cat, Status.SUSPENDED, is_featured=True, business_name="Suspendu Pro")
        resp = self.get()
        self.assertEqual(list(resp.context["featured"]), [shown])
        self.assertContains(resp, "Visible Pro")
        for hidden in ("Pas Mis En Avant", "En Attente Pro", "Suspendu Pro"):
            self.assertNotContains(resp, hidden)

    def test_featured_section_hidden_when_empty(self):
        self.assertNotContains(self.get(), "Artisans à découvrir")

    def test_testimonials_show_positive_visible_reviews_with_masked_name(self):
        p = make_provider(self.cat)
        make_review(p, 5, "Impeccable et ponctuel")
        make_review(p, 2, "Décevant du tout")
        make_review(p, 5, "Avis masqué par modération", status=Review.Status.HIDDEN)
        make_review(p, 5, "")
        resp = self.get()
        self.assertContains(resp, "Impeccable et ponctuel")
        self.assertNotContains(resp, "Décevant du tout")
        self.assertNotContains(resp, "Avis masqué par modération")
        self.assertContains(resp, "Aïcha N.")
        self.assertNotContains(resp, "Ngono")  # le nom de famille n'est jamais publié

    def test_testimonials_hidden_when_none(self):
        self.assertNotContains(self.get(), "Ce que disent les clients")

    def test_faq_section_uses_active_entries_only(self):
        FAQ.objects.create(question="Question affichée ?", answer="Réponse A")
        FAQ.objects.create(question="Question cachée ?", answer="Réponse B", is_active=False)
        resp = self.get()
        self.assertContains(resp, "Question affichée ?")
        self.assertNotContains(resp, "Question cachée ?")

    def test_popular_searches_only_for_existing_cities(self):
        # Seule Douala existe dans le catalogue de test.
        resp = self.get()
        labels = [l for l, _, _ in resp.context["popular_searches"]]
        self.assertIn("Plombier à Douala", labels)
        self.assertNotIn("Couturière à Yaoundé", labels)
        self.assertContains(resp, "q=Plombier&amp;ville=douala")

    def test_cities_list_counts_only_public_providers(self):
        make_provider(self.cat, Status.ACTIVE)
        make_provider(self.cat, Status.PENDING)
        douala = next(c for c in self.get().context["cities"] if c.slug == "douala")
        self.assertEqual(douala.provider_count, 1)

    def test_inactive_city_not_listed(self):
        City.objects.filter(slug="douala").update(is_active=False)
        self.assertEqual(self.get().context["stats"]["cities"], 0)

    def test_navbar_adapts_to_logged_in_user(self):
        resp = self.get()
        self.assertContains(resp, "Inscription")
        self.assertNotContains(resp, "Mon espace")
        provider = make_provider(self.cat)
        self.client.force_login(provider.user)
        resp = self.get()
        self.assertContains(resp, 'href="/prestataire/"')
        self.assertContains(resp, "Mon espace")

    def test_cta_buttons_point_to_role_specific_signup(self):
        resp = self.get()
        self.assertContains(resp, reverse("accounts:signup_client"))
        self.assertContains(resp, reverse("accounts:signup_provider"))

    def test_seo_tags(self):
        resp = self.get()
        self.assertContains(resp, '<link rel="canonical"')
        self.assertContains(resp, 'property="og:title"')
        self.assertContains(resp, "/static/img/og-image.png")
        self.assertContains(resp, '"@type":"SearchAction"')
        self.assertContains(resp, 'content="index,follow"')

    def test_private_pages_are_noindex(self):
        self.assertContains(self.client.get(reverse("accounts:login")), "noindex")

    def test_social_links_only_when_configured(self):
        self.assertNotContains(self.get(), "Réseaux sociaux")
        with override_settings(SOCIAL_LINKS={"facebook": "https://facebook.com/kora", "instagram": ""}):
            resp = self.get()
            self.assertContains(resp, "https://facebook.com/kora")
            self.assertNotContains(resp, "instagram")

    def test_footer_lists_published_pages_only(self):
        StaticPage.objects.create(slug="cgu", title="Conditions générales", body="x")
        StaticPage.objects.create(slug="brouillon", title="Page brouillon", body="x", is_published=False)
        resp = self.get()
        self.assertContains(resp, reverse("cms:page", args=["cgu"]))
        self.assertNotContains(resp, "Page brouillon")

    def test_language_switch_available_in_footer(self):
        self.assertContains(self.get(), reverse("set_language"))

    def test_query_count_does_not_grow_with_data(self):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        def count():
            with CaptureQueriesContext(connection) as q:
                self.get()
            return len(q)

        for _ in range(2):
            make_review(make_provider(self.cat, is_featured=True))
        few = count()
        for _ in range(10):
            make_review(make_provider(self.cat, is_featured=True))
        self.assertEqual(count(), few)


class PublicNameTests(TestCase):
    def test_public_name(self):
        self.assertEqual(User(first_name="Paul", last_name="Tchoumi").public_name, "Paul T.")
        self.assertEqual(User(first_name="Paul").public_name, "Paul")
        self.assertEqual(User().public_name, "Client Kora")


class SeoTests(TestCase):
    def setUp(self):
        make_catalog()
        StaticPage.objects.create(slug="cgu", title="CGU", body="x")
        StaticPage.objects.create(slug="brouillon", title="B", body="x", is_published=False)

    def test_sitemap_lists_categories_and_published_pages(self):
        resp = self.client.get(reverse("sitemap"))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn("/categorie/plomberie/", body)
        self.assertIn("/page/cgu/", body)
        self.assertNotIn("brouillon", body)

    def test_robots_blocks_private_areas_and_points_to_sitemap(self):
        body = self.client.get(reverse("robots")).content.decode()
        for path in ("/compte/", "/prestataire/", "/back-office/"):
            self.assertIn(f"Disallow: {path}", body)
        self.assertIn("/sitemap.xml", body)

    def test_unpublished_page_is_404(self):
        self.assertEqual(self.client.get(reverse("cms:page", args=["brouillon"])).status_code, 404)
        self.assertEqual(self.client.get(reverse("cms:page", args=["cgu"])).status_code, 200)


class BannerDisplayTests(TestCase):
    def test_active_banners_shown_inactive_hidden(self):
        from apps.cms.models import Banner

        Banner.objects.create(title="Soldes de rentrée", link_url="/recherche/", link_label="Voir")
        Banner.objects.create(title="Ancienne annonce", is_active=False)
        html = self.client.get(reverse("core:home")).content.decode()
        self.assertIn("Soldes de rentrée", html)
        self.assertNotIn("Ancienne annonce", html)
