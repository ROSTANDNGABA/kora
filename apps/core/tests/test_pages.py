from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User


class PublicPagesTests(TestCase):
    def test_home_renders_for_anonymous(self):
        resp = self.client.get(reverse("core:home"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Le savoir-faire camerounais")
        self.assertContains(resp, 'id="categories"')

    def test_home_shows_my_space_when_logged_in(self):
        User.objects.create_user("c@kora.cm", "pass12345")
        self.client.login(username="c@kora.cm", password="pass12345")
        resp = self.client.get(reverse("core:home"))
        self.assertContains(resp, "Mon espace")

    def test_login_page_renders(self):
        self.assertEqual(self.client.get(reverse("accounts:login")).status_code, 200)

    @override_settings(DEBUG=True)
    def test_design_system_renders_in_debug(self):
        resp = self.client.get(reverse("core:design_system"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Design system Kora")

    @override_settings(DEBUG=False)
    def test_design_system_hidden_in_production(self):
        self.assertEqual(self.client.get(reverse("core:design_system")).status_code, 404)

    def test_logout_requires_post(self):
        User.objects.create_user("c@kora.cm", "pass12345")
        self.client.login(username="c@kora.cm", password="pass12345")
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.assertEqual(self.client.post(reverse("accounts:logout")).status_code, 302)
