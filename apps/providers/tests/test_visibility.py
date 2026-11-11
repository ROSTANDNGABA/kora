from django.test import TestCase

from apps.core.tests.factories import make_catalog, make_provider
from apps.providers.models import ProviderProfile

Status = ProviderProfile.Status


class ProviderVisibilityTests(TestCase):
    def setUp(self):
        self.cat = make_catalog()

    def test_only_active_providers_are_public(self):
        active = make_provider(self.cat, Status.ACTIVE)
        for st in (Status.PENDING, Status.SUSPENDED, Status.REJECTED):
            make_provider(self.cat, st)
        self.assertEqual(list(ProviderProfile.objects.public()), [active])

    def test_active_provider_with_deactivated_user_is_hidden(self):
        p = make_provider(self.cat, Status.ACTIVE)
        p.user.is_active = False
        p.user.save()
        self.assertFalse(ProviderProfile.objects.public().exists())
        self.assertFalse(ProviderProfile.objects.get(pk=p.pk).is_public)

    def test_slug_is_unique_and_generated(self):
        a = make_provider(self.cat, business_name="Atelier Mballa")
        b = make_provider(self.cat, business_name="Atelier Mballa")
        self.assertEqual(a.slug, "atelier-mballa")
        self.assertEqual(b.slug, "atelier-mballa-2")
