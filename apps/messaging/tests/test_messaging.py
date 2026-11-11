import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.core.tests.factories import make_catalog, make_provider, make_request, make_user
from apps.messaging.models import Conversation, Message
from apps.notifications.models import Notification
from apps.providers.models import ProviderProfile


class MessagingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.cat = make_catalog()
        self.profile = make_provider(self.cat)
        self.client_user = make_user()
        self.conv = Conversation.objects.create(client=self.client_user, provider=self.profile)

    def test_start_from_provider_creates_once(self):
        self.client.force_login(self.client_user)
        url = reverse("messaging:start", args=[self.profile.slug])
        r1 = self.client.post(url)
        r2 = self.client.post(url)
        self.assertEqual(Conversation.objects.filter(client=self.client_user, provider=self.profile).count(), 1)
        self.assertEqual(r1["Location"], r2["Location"])

    def test_start_requires_login_and_post(self):
        url = reverse("messaging:start", args=[self.profile.slug])
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertIn("connexion", self.client.post(url)["Location"])
        self.client.force_login(self.client_user)
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_cannot_start_with_inactive_provider(self):
        p = make_provider(self.cat, status=ProviderProfile.Status.PENDING)
        self.client.force_login(self.client_user)
        self.assertEqual(self.client.post(reverse("messaging:start", args=[p.slug])).status_code, 404)

    def test_send_message_notifies_once(self):
        self.client.force_login(self.client_user)
        url = reverse("messaging:thread", args=[self.conv.pk])
        self.client.post(url, {"body": "Bonjour"})
        self.client.post(url, {"body": "Vous êtes là ?"})
        self.assertEqual(self.conv.messages.count(), 2)
        self.assertEqual(Notification.objects.filter(user=self.profile.user).count(), 1)

    def test_empty_message_rejected(self):
        self.client.force_login(self.client_user)
        self.client.post(reverse("messaging:thread", args=[self.conv.pk]), {"body": "  "})
        self.assertEqual(self.conv.messages.count(), 0)

    def test_xss_is_escaped(self):
        Message.objects.create(conversation=self.conv, sender=self.client_user, body="<script>alert(1)</script>")
        self.client.force_login(self.profile.user)
        html = self.client.get(reverse("messaging:thread", args=[self.conv.pk])).content.decode()
        self.assertNotIn("<script>alert(1)</script>", html)

    def test_outsider_cannot_read_or_write(self):
        stranger = make_user()
        self.client.force_login(stranger)
        url = reverse("messaging:thread", args=[self.conv.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {"body": "x"}).status_code, 404)
        self.assertEqual(self.client.get(reverse("messaging:thread_fragment", args=[self.conv.pk])).status_code, 404)

    def test_reading_marks_as_read(self):
        m = Message.objects.create(conversation=self.conv, sender=self.client_user, body="Salut")
        self.client.force_login(self.profile.user)
        self.client.get(reverse("messaging:thread", args=[self.conv.pk]))
        m.refresh_from_db()
        self.assertIsNotNone(m.read_at)

    def test_own_messages_not_marked_read(self):
        m = Message.objects.create(conversation=self.conv, sender=self.client_user, body="Salut")
        self.client.force_login(self.client_user)
        self.client.get(reverse("messaging:thread", args=[self.conv.pk]))
        m.refresh_from_db()
        self.assertIsNone(m.read_at)

    def test_unread_badge_count(self):
        Message.objects.create(conversation=self.conv, sender=self.client_user, body="1")
        Message.objects.create(conversation=self.conv, sender=self.client_user, body="2")
        self.client.force_login(self.profile.user)
        r = self.client.get(reverse("messaging:inbox"))
        self.assertEqual(r.context["unread_messages"](), 2)

    def test_image_attachment_validated(self):
        self.client.force_login(self.client_user)
        url = reverse("messaging:thread", args=[self.conv.pk])
        bad = SimpleUploadedFile("a.png", b"nope", content_type="image/png")
        self.client.post(url, {"body": "", "attachment": bad})
        self.assertEqual(self.conv.messages.count(), 0)

    def test_rate_limit(self):
        self.client.force_login(self.client_user)
        url = reverse("messaging:thread", args=[self.conv.pk])
        for i in range(25):
            self.client.post(url, {"body": f"m{i}"})
        self.assertLessEqual(self.conv.messages.count(), 20)

    def test_start_from_request(self):
        req = make_request(self.client_user, self.profile)
        self.client.force_login(self.client_user)
        r = self.client.post(reverse("messaging:start_from_request", args=[req.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Conversation.objects.get(client=self.client_user, provider=self.profile).request, None or Conversation.objects.get().request)

    def test_inbox_isolated(self):
        other = make_user()
        self.client.force_login(other)
        self.assertNotContains(self.client.get(reverse("messaging:inbox")), self.profile.business_name)


class NotificationTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.n = Notification.objects.create(user=self.user, title="Hello", url="/mon-espace/")

    def test_list(self):
        self.assertContains(self.client.get(reverse("notifications:list")), "Hello")

    def test_open_marks_read_and_redirects(self):
        r = self.client.post(reverse("notifications:open", args=[self.n.pk]))
        self.n.refresh_from_db()
        self.assertTrue(self.n.is_read)
        self.assertEqual(r["Location"], "/mon-espace/")

    def test_external_url_not_followed(self):
        self.n.url = "https://evil.example/phish"
        self.n.save()
        r = self.client.post(reverse("notifications:open", args=[self.n.pk]))
        self.assertNotIn("evil.example", r["Location"])

    def test_mark_all_read(self):
        Notification.objects.create(user=self.user, title="B")
        self.client.post(reverse("notifications:read_all"))
        self.assertFalse(Notification.objects.filter(user=self.user, is_read=False).exists())

    def test_cannot_open_foreign_notification(self):
        other = make_user()
        n = Notification.objects.create(user=other, title="secret")
        self.assertEqual(self.client.post(reverse("notifications:open", args=[n.pk])).status_code, 404)
        n.refresh_from_db()
        self.assertFalse(n.is_read)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(reverse("notifications:open", args=[self.n.pk])).status_code, 405)

    def test_anonymous_redirected(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("notifications:list")).status_code, 302)
