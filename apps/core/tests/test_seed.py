from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.catalog.models import Category, City
from apps.providers.models import ProviderProfile
from apps.reviews.models import Review


class SeedDemoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def test_catalog_and_volumes(self):
        self.assertEqual(Category.objects.count(), 10)
        self.assertEqual(City.objects.count(), 9)
        self.assertEqual(ProviderProfile.objects.count(), 40)
        self.assertGreaterEqual(Review.objects.count(), 40)

    def test_expected_subcategories(self):
        couture = Category.objects.get(slug="couture-stylisme")
        self.assertEqual(
            sorted(couture.subcategories.values_list("name", flat=True)),
            sorted(["Couturiers", "Couturières", "Stylistes", "Retouches", "Modélistes"]),
        )

    def test_provider_statuses_cover_admin_queue(self):
        statuses = set(ProviderProfile.objects.values_list("status", flat=True))
        self.assertEqual(statuses, {"ACTIVE", "PENDING", "SUSPENDED", "REJECTED"})
        self.assertEqual(ProviderProfile.objects.public().count(), ProviderProfile.objects.filter(status="ACTIVE").count())

    def test_demo_accounts_log_in_and_land_on_their_space(self):
        expected = {
            "admin@kora.cm": reverse("dashboard_admin:home"),
            "prestataire@kora.cm": reverse("dashboard_provider:home"),
            "client@kora.cm": reverse("core:client_home"),
        }
        for email, url in expected.items():
            resp = self.client.post(reverse("accounts:login"), {"username": email, "password": "Kora2026!"})
            self.assertRedirects(resp, url, fetch_redirect_response=False, msg_prefix=email)
            self.client.logout()

    def test_demo_provider_is_active_and_has_requests(self):
        p = ProviderProfile.objects.get(user__email="prestataire@kora.cm")
        self.assertEqual(p.status, "ACTIVE")
        self.assertEqual(p.category.slug, "plomberie")
        self.assertEqual(set(p.service_requests.values_list("status", flat=True)), {
            "SENT", "VIEWED", "QUOTED", "ACCEPTED", "IN_PROGRESS", "DONE", "CANCELLED", "REFUSED",
        })

    def test_rating_excludes_hidden_reviews(self):
        for p in ProviderProfile.objects.filter(reviews_count__gt=0):
            visible = p.reviews.filter(status="VISIBLE")
            self.assertEqual(p.reviews_count, visible.count())

    def test_second_run_requires_reset(self):
        with self.assertRaises(CommandError):
            call_command("seed_demo", verbosity=0)
        call_command("seed_demo", "--reset", verbosity=0)
        self.assertEqual(User.objects.filter(email="admin@kora.cm").count(), 1)
        self.assertEqual(ProviderProfile.objects.count(), 40)

    def test_home_lists_the_ten_categories(self):
        resp = self.client.get(reverse("core:home"))
        for c in Category.objects.all():
            self.assertContains(resp, c.name.replace("&", "&amp;"))
