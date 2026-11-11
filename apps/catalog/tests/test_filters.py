from django.test import TestCase
from django.urls import reverse

from apps.core.tests.factories import make_catalog, make_provider, make_user
from apps.favorites.models import SavedSearch
from apps.providers.models import ProviderProfile, Service

URL = "catalog:search"


class FilterTests(TestCase):
    def setUp(self):
        self.cat = make_catalog()
        self.top = make_provider(self.cat, business_name="Top Pro", rating_avg=4.8, reviews_count=20, is_verified=True)
        self.mid = make_provider(self.cat, business_name="Mid Pro", rating_avg=3.4, reviews_count=5)
        self.new = make_provider(self.cat, business_name="Nouveau Pro")

    def names(self, **params):
        resp = self.client.get(reverse(URL), params)
        self.assertEqual(resp.status_code, 200)
        return [p.business_name for p in resp.context["results"]]

    def test_min_rating_excludes_unrated_and_lower(self):
        self.assertEqual(self.names(note="4"), ["Top Pro"])
        self.assertEqual(sorted(self.names(note="3")), ["Mid Pro", "Top Pro"])

    def test_unsupported_rating_value_is_ignored(self):
        self.assertEqual(len(self.names(note="4.9")), 3)
        self.assertEqual(len(self.names(note="abc")), 3)

    def test_verified_only(self):
        self.assertEqual(self.names(verifie="1"), ["Top Pro"])

    def test_max_price_uses_active_priced_services(self):
        Service.objects.create(provider=self.top, title="Cher", amount=50000)
        Service.objects.create(provider=self.mid, title="Pas cher", amount=8000)
        Service.objects.create(provider=self.new, title="Inactif", amount=1000, is_active=False)
        self.assertEqual(self.names(prix_max="10000"), ["Mid Pro"])
        self.assertEqual(sorted(self.names(prix_max="60000")), ["Mid Pro", "Top Pro"])

    def test_invalid_price_is_ignored(self):
        self.assertEqual(len(self.names(prix_max="-5")), 3)
        self.assertEqual(len(self.names(prix_max="beaucoup")), 3)

    def test_sorting(self):
        self.assertEqual(self.names(tri="note")[:2], ["Top Pro", "Mid Pro"])
        self.assertEqual(self.names(tri="avis")[:2], ["Top Pro", "Mid Pro"])
        self.assertEqual(self.names(tri="recents")[0], "Nouveau Pro")
        self.assertEqual(len(self.names(tri="nimportequoi")), 3)  # tri inconnu : ordre par défaut

    def test_subcategory_implies_category(self):
        self.top.subcategories.add(self.cat["plombier"])
        resp = self.client.get(reverse(URL), {"specialite": "plombier"})
        self.assertEqual(resp.context["filters"].category, self.cat["plomberie"])
        self.assertEqual([p.business_name for p in resp.context["results"]], ["Top Pro"])

    def test_combined_filters(self):
        self.assertEqual(self.names(note="3", verifie="1", ville="douala", tri="note"), ["Top Pro"])


class HtmxTests(TestCase):
    def setUp(self):
        self.cat = make_catalog()
        make_provider(self.cat, business_name="Aqua Services")

    def test_htmx_request_returns_fragment_only(self):
        resp = self.client.get(reverse(URL), {"q": "aqua"}, HTTP_HX_REQUEST="true")
        self.assertTemplateUsed(resp, "catalog/partials/results.html")
        self.assertNotContains(resp, "<html")
        self.assertContains(resp, "Aqua Services")
        self.assertIn("HX-Request", resp["Vary"])

    def test_normal_request_returns_full_page_with_hx_attributes(self):
        resp = self.client.get(reverse(URL))
        self.assertContains(resp, "<html")
        self.assertContains(resp, 'hx-target="#results"')

    def test_category_page_also_supports_fragment(self):
        resp = self.client.get(reverse("catalog:category", args=["plomberie"]), HTTP_HX_REQUEST="true")
        self.assertNotContains(resp, "<html")
        self.assertContains(resp, "Aqua Services")

    def test_filtered_pages_are_noindex(self):
        self.assertContains(self.client.get(reverse(URL), {"q": "aqua"}), "noindex,follow")
        self.assertContains(self.client.get(reverse(URL)), "index,follow")

    def test_typing_same_search_twice_logs_once(self):
        from apps.catalog.models import SearchQuery

        self.client.get(reverse(URL), {"q": "aqua"})
        self.client.get(reverse(URL), {"q": "aqua", "note": "4"}, HTTP_HX_REQUEST="true")
        self.assertEqual(SearchQuery.objects.count(), 1)
        self.client.get(reverse(URL), {"q": "plombier"})
        self.assertEqual(SearchQuery.objects.count(), 2)


class SaveSearchButtonTests(TestCase):
    def setUp(self):
        self.cat = make_catalog()
        make_provider(self.cat)

    def test_anonymous_sees_login_link(self):
        resp = self.client.get(reverse(URL), {"q": "plombier"})
        self.assertContains(resp, "Se connecter pour enregistrer")

    def test_client_sees_save_button_then_saved_badge(self):
        user = make_user()
        self.client.force_login(user)
        resp = self.client.get(reverse(URL), {"q": "plombier"})
        self.assertContains(resp, "Enregistrer cette recherche")
        SavedSearch.objects.create(user=user, label="x", query_string="q=plombier")
        resp = self.client.get(reverse(URL), {"q": "plombier"})
        self.assertContains(resp, "Recherche enregistrée")

    def test_no_button_without_criteria(self):
        self.client.force_login(make_user())
        self.assertNotContains(self.client.get(reverse(URL)), "Enregistrer cette recherche")

    def test_provider_never_sees_save_button(self):
        self.client.force_login(ProviderProfile.objects.first().user)
        resp = self.client.get(reverse(URL), {"q": "plombier"})
        self.assertNotContains(resp, "Enregistrer cette recherche")
        self.assertNotContains(resp, "Se connecter pour enregistrer")
