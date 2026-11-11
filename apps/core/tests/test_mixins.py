from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import PermissionDenied
from django.contrib.auth.models import AnonymousUser
from django.views import View

from apps.accounts.models import User
from apps.core.mixins import RoleRequiredMixin


class ProviderOnlyView(RoleRequiredMixin, View):
    allowed_roles = (User.Role.PROVIDER,)

    def get(self, request):
        return HttpResponse("ok")


class StrictView(ProviderOnlyView):
    raise_on_denied = True


class RoleRequiredMixinTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def _request(self, user):
        request = self.rf.get("/x/")
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))
        request.user = user
        return request

    def test_anonymous_redirected_to_login(self):
        resp = ProviderOnlyView.as_view()(self._request(AnonymousUser()))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/compte/connexion/", resp["Location"])

    def test_wrong_role_redirected_to_own_space(self):
        client = User.objects.create_user("c@kora.cm", "pass12345")
        resp = ProviderOnlyView.as_view()(self._request(client))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], client.get_home_url())

    def test_wrong_role_can_raise_403(self):
        client = User.objects.create_user("c@kora.cm", "pass12345")
        with self.assertRaises(PermissionDenied):
            StrictView.as_view()(self._request(client))

    def test_allowed_role_passes(self):
        provider = User.objects.create_user("p@kora.cm", "pass12345", role=User.Role.PROVIDER)
        resp = ProviderOnlyView.as_view()(self._request(provider))
        self.assertEqual(resp.status_code, 200)

    def test_inactive_user_denied(self):
        provider = User.objects.create_user("p@kora.cm", "pass12345", role=User.Role.PROVIDER, is_active=False)
        resp = ProviderOnlyView.as_view()(self._request(provider))
        self.assertEqual(resp.status_code, 302)
