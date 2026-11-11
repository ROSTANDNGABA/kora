from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.catalog.models import Category, City, SearchQuery, Subcategory
from apps.core.tests.factories import make_catalog, make_provider
from apps.providers.models import ProviderProfile
from apps.providers.selectors import search_providers

Status = ProviderProfile.Status


class SearchSelectorTests(TestCase):
    def setUp(self):
        self.cat = make_catalog()
        self.yaounde = City.objects.create(name="Yaoundé", slug="yaounde")
        self.couturieres = Subcategory.objects.create(category=self.cat["couture"], name="Couturières", slug="couturieres")
        self.p_douala = make_provider(self.cat, business_name="Aqua Services")
        self.p_douala.subcategories.add(self.cat["plombier"])
        self.p_couture = make_provider(self.cat, business_name="Mode Chantal")
        self.p_couture.category = self.cat["couture"]
        self.p_couture.city = self.yaounde
        self.p_couture.save()
        self.p_couture.subcategories.add(self.couturieres)

    def names(self, **kw):
        return sorted(p.business_name for p in search_providers(**kw))

    def test_accent_and_case_insensitive(self):
        for q in ("couturiere", "COUTURIÈRE", "Couturières", "couturieres"):
            self.assertEqual(self.names(q=q), ["Mode Chantal"], q)

    def test_matches_trade_category_or_business_name(self):
        self.assertEqual(self.names(q="plombier"), ["Aqua Services"])
        self.assertEqual(self.names(q="plomberie"), ["Aqua Services"])
        self.assertEqual(self.names(q="aqua"), ["Aqua Services"])

    def test_city_filter(self):
        self.assertEqual(self.names(city=self.yaounde), ["Mode Chantal"])
        self.assertEqual(self.names(city=self.cat["city"]), ["Aqua Services"])
        self.assertEqual(self.names(q="couturiere", city=self.cat["city"]), [])

    def test_category_and_subcategory_filters(self):
        self.assertEqual(self.names(category=self.cat["couture"]), ["Mode Chantal"])
        self.assertEqual(self.names(subcategory=self.cat["plombier"]), ["Aqua Services"])

    def test_non_public_providers_never_returned(self):
        for st in (Status.PENDING, Status.SUSPENDED, Status.REJECTED):
            make_provider(self.cat, st, business_name=f"Cache {st}")
        self.assertEqual(sorted(self.names()), ["Aqua Services", "Mode Chantal"])
        self.assertEqual(self.names(q="cache"), [])

    def test_no_duplicates_when_several_subcategories_match(self):
        extra = Subcategory.objects.create(category=self.cat["plomberie"], name="Plomberie sanitaire", slug="plomberie-sanitaire")
        self.p_douala.subcategories.add(extra)
        self.assertEqual(self.names(q="plomb"), ["Aqua Services"])

    def test_ordering_puts_verified_then_best_rated_first(self):
        better = make_provider(self.cat, business_name="Zeta Pro", is_verified=True, rating_avg=4.5, reviews_count=10)
        self.assertEqual(search_providers(city=self.cat["city"]).first(), better)


class SearchViewTests(TestCase):
    def setUp(self):
        self.cat = make_catalog()
        self.p = make_provider(self.cat, business_name="Aqua Services")

    def test_page_renders_and_lists_results(self):
        resp = self.client.get(reverse("catalog:search"), {"q": "aqua"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Aqua Services")
        self.assertContains(resp, "1 prestataire trouvé")

    def test_empty_search_lists_all_public_providers(self):
        make_provider(self.cat, Status.PENDING, business_name="Invisible")
        resp = self.client.get(reverse("catalog:search"))
        self.assertContains(resp, "Aqua Services")
        self.assertNotContains(resp, "Invisible")

    def test_no_results_shows_empty_state_and_category_links(self):
        resp = self.client.get(reverse("catalog:search"), {"q": "zzzzz"})
        self.assertContains(resp, "Aucun résultat")
        self.assertContains(resp, reverse("catalog:category", args=["plomberie"]))

    def test_unknown_city_param_is_ignored(self):
        resp = self.client.get(reverse("catalog:search"), {"ville": "inconnue"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Aqua Services")

    def test_search_is_logged_with_result_count(self):
        self.client.get(reverse("catalog:search"), {"q": "aqua", "ville": "douala"})
        self.client.get(reverse("catalog:search"), {"q": "zzzzz"})
        logs = {s.query: s for s in SearchQuery.objects.all()}
        self.assertEqual(logs["aqua"].results_count, 1)
        self.assertEqual(logs["aqua"].city.slug, "douala")
        self.assertEqual(logs["zzzzz"].results_count, 0)

    def test_empty_query_and_page_two_are_not_logged(self):
        for i in range(14):
            make_provider(self.cat, business_name=f"Atelier {i:02d}")
        self.client.get(reverse("catalog:search"))
        self.client.get(reverse("catalog:search"), {"q": "atelier", "page": "2"})
        self.assertEqual(SearchQuery.objects.count(), 0)

    def test_html_in_query_is_escaped(self):
        resp = self.client.get(reverse("catalog:search"), {"q": "<script>alert(1)</script>"})
        self.assertNotContains(resp, "<script>alert(1)</script>")

    def test_pagination(self):
        for i in range(14):
            make_provider(self.cat, business_name=f"Pro {i:02d}")
        resp = self.client.get(reverse("catalog:search"))
        self.assertEqual(len(resp.context["results"]), 12)
        self.assertContains(resp, "Page 1 sur 2")
        resp = self.client.get(reverse("catalog:search"), {"page": 2})
        self.assertEqual(len(resp.context["results"]), 3)
        self.assertEqual(self.client.get(reverse("catalog:search"), {"page": "abc"}).status_code, 200)

    def test_query_count_does_not_grow_with_results(self):
        def count():
            with CaptureQueriesContext(connection) as q:
                self.client.get(reverse("catalog:search"))
            return len(q)

        for _ in range(2):
            p = make_provider(self.cat)
            p.subcategories.add(self.cat["plombier"])
        few = count()
        for _ in range(8):
            p = make_provider(self.cat)
            p.subcategories.add(self.cat["plombier"])
        self.assertEqual(count(), few)


class CategoryViewTests(TestCase):
    def setUp(self):
        self.cat = make_catalog()
        self.plombier = make_provider(self.cat, business_name="Plombier Un")
        self.plombier.subcategories.add(self.cat["plombier"])
        self.other = make_provider(self.cat, business_name="Plombier Deux")
        self.couturier = make_provider(self.cat, business_name="Couture Un")
        self.couturier.category = self.cat["couture"]
        self.couturier.save()

    def url(self, slug="plomberie"):
        return reverse("catalog:category", args=[slug])

    def test_lists_only_that_category(self):
        resp = self.client.get(self.url())
        self.assertContains(resp, "Plombier Un")
        self.assertContains(resp, "Plombier Deux")
        self.assertNotContains(resp, "Couture Un")

    def test_subcategory_tab_filters(self):
        resp = self.client.get(self.url(), {"specialite": "plombier"})
        self.assertContains(resp, "Plombier Un")
        self.assertNotContains(resp, "Plombier Deux")
        self.assertEqual(resp.context["subcategory"], self.cat["plombier"])

    def test_city_filter(self):
        yaounde = City.objects.create(name="Yaoundé", slug="yaounde")
        self.other.city = yaounde
        self.other.save()
        resp = self.client.get(self.url(), {"ville": "yaounde"})
        self.assertContains(resp, "Plombier Deux")
        self.assertNotContains(resp, "Plombier Un")

    def test_unknown_or_inactive_category_is_404(self):
        self.assertEqual(self.client.get(self.url("nope")).status_code, 404)
        Category.objects.filter(slug="plomberie").update(is_active=False)
        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_empty_category_shows_empty_state(self):
        Category.objects.create(name="Poterie", slug="poterie")
        self.assertContains(self.client.get(self.url("poterie")), "Aucun résultat")

    def test_shows_artisan_signup_banner(self):
        self.assertContains(self.client.get(self.url()), reverse("accounts:signup_provider"))
