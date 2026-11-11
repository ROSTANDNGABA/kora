from django.test import TestCase
from django.urls import reverse

from apps.core.tests.factories import make_catalog, make_provider, make_user
from apps.favorites.models import Favorite, SavedSearch
from apps.providers.models import ProviderProfile

Status = ProviderProfile.Status


class FavoriteToggleTests(TestCase):
    def setUp(self):
        self.cat = make_catalog()
        self.provider = make_provider(self.cat, business_name="Aqua Services")
        self.user = make_user()
        self.url = reverse("favorites:toggle", args=[self.provider.pk])

    def test_toggle_adds_then_removes(self):
        self.client.force_login(self.user)
        self.client.post(self.url)
        self.assertTrue(Favorite.objects.filter(user=self.user, provider=self.provider).exists())
        self.client.post(self.url)
        self.assertFalse(Favorite.objects.filter(user=self.user).exists())

    def test_htmx_returns_heart_fragment_with_new_state(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, HTTP_HX_REQUEST="true")
        self.assertContains(resp, 'aria-pressed="true"')
        resp = self.client.post(self.url, HTTP_HX_REQUEST="true")
        self.assertContains(resp, 'aria-pressed="false"')
        self.assertNotContains(resp, "<html")

    def test_removing_from_list_returns_empty_so_card_disappears(self):
        Favorite.objects.create(user=self.user, provider=self.provider)
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {"from": "list"}, HTTP_HX_REQUEST="true")
        self.assertEqual(resp.content, b"")

    def test_get_not_allowed(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_anonymous_redirected_to_login(self):
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("accounts:login"), resp["Location"])
        self.assertFalse(Favorite.objects.exists())

    def test_provider_cannot_favorite(self):
        self.client.force_login(make_provider(self.cat).user)
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Favorite.objects.exists())

    def test_non_public_provider_404(self):
        hidden = make_provider(self.cat, Status.SUSPENDED)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse("favorites:toggle", args=[hidden.pk])).status_code, 404)

    def test_non_js_post_redirects_back_safely(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {"next": "https://evil.example/"})
        self.assertEqual(resp["Location"], self.provider.get_absolute_url())
        resp = self.client.post(self.url, {"next": "/recherche/?q=x"})
        self.assertEqual(resp["Location"], "/recherche/?q=x")

    def test_hearts_on_cards_reflect_state_by_role(self):
        search = reverse("catalog:search")
        self.assertContains(self.client.get(search), "Se connecter pour ajouter")
        self.client.force_login(self.user)
        self.assertContains(self.client.get(search), 'aria-pressed="false"')
        Favorite.objects.create(user=self.user, provider=self.provider)
        self.assertContains(self.client.get(search), 'aria-pressed="true"')
        self.client.force_login(make_provider(self.cat).user)
        resp = self.client.get(search)
        self.assertNotContains(resp, "aria-pressed")
        self.assertNotContains(resp, "Se connecter pour ajouter")

    def test_cards_cost_one_favorite_query_whatever_the_count(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self.client.force_login(self.user)

        def fav_queries():
            with CaptureQueriesContext(connection) as q:
                self.client.get(reverse("catalog:search"))
            return len([x for x in q if "favorites_favorite" in x["sql"]])

        for _ in range(5):
            make_provider(self.cat)
        self.assertEqual(fav_queries(), 1)


class FavoriteListTests(TestCase):
    def setUp(self):
        self.cat = make_catalog()
        self.user = make_user()
        self.client.force_login(self.user)

    def test_lists_favorites_newest_first_and_hides_non_public(self):
        a, b = make_provider(self.cat, business_name="Alpha"), make_provider(self.cat, business_name="Bravo")
        gone = make_provider(self.cat, business_name="Suspendu")
        for p in (a, b, gone):
            Favorite.objects.create(user=self.user, provider=p)
        gone.status = Status.SUSPENDED
        gone.save()
        resp = self.client.get(reverse("favorites:list"))
        self.assertEqual([p.business_name for p in resp.context["providers"]], ["Bravo", "Alpha"])
        self.assertNotContains(resp, "Suspendu")

    def test_other_users_favorites_not_shown(self):
        p = make_provider(self.cat, business_name="Secret")
        Favorite.objects.create(user=make_user(), provider=p)
        self.assertNotContains(self.client.get(reverse("favorites:list")), "Secret")

    def test_empty_states(self):
        self.assertContains(self.client.get(reverse("favorites:list")), "Aucun favori pour le moment")
        self.assertContains(self.client.get(reverse("favorites:list"), {"onglet": "recherches"}), "Aucune recherche enregistrée")

    def test_list_requires_client_role(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("favorites:list")).status_code, 302)
        self.client.force_login(make_provider(self.cat).user)
        resp = self.client.get(reverse("favorites:list"))
        self.assertRedirects(resp, reverse("dashboard_provider:home"), fetch_redirect_response=False)


class SavedSearchTests(TestCase):
    def setUp(self):
        self.cat = make_catalog()
        self.user = make_user()
        self.client.force_login(self.user)

    def save(self, qs, label="Plombier à Douala", **extra):
        return self.client.post(reverse("favorites:save_search"), {"query_string": qs, "label": label}, **extra)

    def test_save_and_list(self):
        self.save("q=plombier&ville=douala")
        s = SavedSearch.objects.get()
        self.assertEqual(s.query_string, "q=plombier&ville=douala")
        resp = self.client.get(reverse("favorites:list"), {"onglet": "recherches"})
        self.assertContains(resp, "Plombier à Douala")
        self.assertContains(resp, "/recherche/?q=plombier&amp;ville=douala")

    def test_unknown_parameters_are_dropped(self):
        self.save("q=plombier&evil=1&page=3&ville=douala")
        self.assertEqual(SavedSearch.objects.get().query_string, "q=plombier&ville=douala")

    def test_empty_criteria_rejected(self):
        self.save("evil=1")
        self.assertFalse(SavedSearch.objects.exists())

    def test_saving_twice_keeps_one(self):
        self.save("q=plombier")
        self.save("q=plombier")
        self.assertEqual(SavedSearch.objects.count(), 1)

    def test_htmx_save_returns_badge(self):
        resp = self.save("q=plombier", HTTP_HX_REQUEST="true")
        self.assertContains(resp, "Recherche enregistrée")

    def test_limit(self):
        for i in range(30):
            SavedSearch.objects.create(user=self.user, label=str(i), query_string=f"q=m{i}")
        self.save("q=nouveau")
        self.assertEqual(SavedSearch.objects.filter(user=self.user).count(), 30)

    def test_delete_own_only(self):
        mine = SavedSearch.objects.create(user=self.user, label="a", query_string="q=a")
        theirs = SavedSearch.objects.create(user=make_user(), label="b", query_string="q=b")
        self.assertEqual(self.client.post(reverse("favorites:delete_search", args=[theirs.pk])).status_code, 404)
        self.client.post(reverse("favorites:delete_search", args=[mine.pk]))
        self.assertFalse(SavedSearch.objects.filter(pk=mine.pk).exists())
        self.assertTrue(SavedSearch.objects.filter(pk=theirs.pk).exists())
