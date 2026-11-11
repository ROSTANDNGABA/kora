"""Contrôles de sécurité transverses : en-têtes, CSRF, isolation entre comptes, échappement, robots."""
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.tests.factories import make_catalog, make_provider, make_request, make_user
from apps.messaging.models import Conversation
from apps.providers.models import ProviderProfile


class HeadersTests(TestCase):
    def test_security_headers_on_public_page(self):
        r = self.client.get(reverse("core:home"))
        csp = r["Content-Security-Policy"]
        for directive in ("default-src 'self'", "object-src 'none'", "frame-ancestors 'none'", "base-uri 'self'"):
            self.assertIn(directive, csp)
        self.assertIn("camera=()", r["Permissions-Policy"])
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
        self.assertEqual(r["X-Frame-Options"], "DENY")
        self.assertEqual(r["Referrer-Policy"], "same-origin")

    def test_no_external_resources_in_pages(self):
        html = self.client.get(reverse("core:home")).content.decode()
        for host in ("cdn.", "googleapis", "cloudflare", "unpkg", "jsdelivr"):
            self.assertNotIn(host, html)

    def test_private_areas_never_cached(self):
        user = make_user(User.Role.ADMIN, is_superuser=True)
        self.client.force_login(user)
        for path in (reverse("dashboard_admin:home"), reverse("notifications:list"), reverse("messaging:inbox")):
            self.assertEqual(self.client.get(path)["Cache-Control"], "private, no-store", path)

    def test_robots_hides_private_areas(self):
        body = self.client.get("/robots.txt").content.decode()
        for path in ("/back-office/", "/prestataire/", "/messages/", "/notifications/", "/mon-espace/"):
            self.assertIn(f"Disallow: {path}", body)

    def test_dashboards_are_noindex(self):
        user = make_user(User.Role.ADMIN, is_superuser=True)
        self.client.force_login(user)
        self.assertIn("noindex", self.client.get(reverse("dashboard_admin:home")).content.decode())


class CsrfTests(TestCase):
    def test_state_changing_endpoints_reject_missing_token(self):
        cat = make_catalog()
        pro = make_provider(cat)
        customer = make_user()
        admin = make_user(User.Role.ADMIN, is_superuser=True)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(customer)
        self.assertEqual(strict.post(reverse("messaging:start", args=[pro.slug])).status_code, 403)
        self.assertEqual(strict.post(reverse("notifications:read_all")).status_code, 403)
        strict.force_login(admin)
        self.assertEqual(strict.post(reverse("dashboard_admin:provider_approve", args=[pro.pk])).status_code, 403)
        strict.force_login(pro.user)
        self.assertEqual(strict.post(reverse("dashboard_provider:service_new"), {"title": "x"}).status_code, 403)


class IsolationTests(TestCase):
    """Chaque compte ne voit et ne modifie que ses propres données."""

    def setUp(self):
        cache.clear()
        self.cat = make_catalog()
        self.pro_a, self.pro_b = make_provider(self.cat), make_provider(self.cat)
        self.alice, self.bob = make_user(), make_user()
        self.req_alice = make_request(self.alice, self.pro_a)

    def test_client_cannot_open_other_clients_request(self):
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get(reverse("requests_app:detail", args=[self.req_alice.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("requests_app:cancel", args=[self.req_alice.pk])).status_code, 404)

    def test_provider_cannot_open_other_providers_request(self):
        self.client.force_login(self.pro_b.user)
        self.assertEqual(self.client.get(reverse("dashboard_provider:request_detail", args=[self.req_alice.pk])).status_code, 404)

    def test_conversation_private_to_its_two_parties(self):
        conv = Conversation.objects.create(client=self.alice, provider=self.pro_a)
        for user in (self.bob, self.pro_b.user):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("messaging:thread", args=[conv.pk])).status_code, 404)

    def test_roles_cannot_cross_dashboards(self):
        self.client.force_login(self.alice)
        self.assertNotEqual(self.client.get(reverse("dashboard_provider:home")).status_code, 200)
        self.assertNotEqual(self.client.get(reverse("dashboard_admin:home")).status_code, 200)
        self.client.force_login(self.pro_a.user)
        self.assertNotEqual(self.client.get(reverse("dashboard_admin:home")).status_code, 200)
        self.assertNotEqual(self.client.get(reverse("core:client_home")).status_code, 200)

    def test_private_media_not_reachable_by_url(self):
        from django.conf import settings

        self.assertNotEqual(settings.PRIVATE_MEDIA_ROOT, settings.MEDIA_ROOT)
        self.assertEqual(self.client.get("/media/verifications/cni.pdf").status_code, 404)


class XssTests(TestCase):
    PAYLOAD = '<script>alert("x")</script>'

    def test_user_content_is_escaped_everywhere_it_is_displayed(self):
        cat = make_catalog()
        pro = make_provider(cat, business_name=self.PAYLOAD, description=self.PAYLOAD)
        customer = make_user(first_name=self.PAYLOAD)
        req = make_request(customer, pro, description=self.PAYLOAD)
        admin = make_user(User.Role.ADMIN, is_superuser=True)
        pages = [
            (admin, reverse("dashboard_admin:provider_detail", args=[pro.pk])),
            (admin, reverse("dashboard_admin:client_detail", args=[customer.pk])),
            (admin, reverse("dashboard_admin:request_detail", args=[req.pk])),
            (admin, reverse("dashboard_admin:search") + "?q=script"),
            (pro.user, reverse("dashboard_provider:request_detail", args=[req.pk])),
            (pro.user, reverse("dashboard_provider:home")),
        ]
        for user, path in pages:
            self.client.force_login(user)
            html = self.client.get(path).content.decode()
            self.assertNotIn(self.PAYLOAD, html, path)
        self.client.logout()
        pro.status = ProviderProfile.Status.ACTIVE
        pro.save()
        self.assertNotIn(self.PAYLOAD, self.client.get(pro.get_absolute_url()).content.decode())


class SessionTests(TestCase):
    def test_logout_requires_post(self):
        self.client.force_login(make_user())
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)

    def test_suspended_user_loses_access_immediately(self):
        user = make_user()
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("core:client_home")).status_code, 200)
        user.is_active = False
        user.save()
        self.assertEqual(self.client.get(reverse("core:client_home")).status_code, 302)
