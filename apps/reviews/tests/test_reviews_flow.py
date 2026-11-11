from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.tests.factories import make_catalog, make_provider, make_request, make_user
from apps.notifications.models import Notification
from apps.providers.models import ProviderProfile
from apps.requests_app.models import ServiceRequest
from apps.reviews.models import Report, Review

S = ServiceRequest.Status


class ReviewFlowTests(TestCase):
    def setUp(self):
        self.cat = make_catalog()
        self.provider = make_provider(self.cat)
        self.user = make_user()
        self.client.force_login(self.user)
        self.req = make_request(self.user, self.provider, S.DONE)
        self.url = reverse("reviews:create", args=[self.req.pk])

    def test_review_created_updates_rating_and_notifies(self):
        resp = self.client.post(self.url, {"rating": 4, "comment": "  Bon travail  "})
        self.assertRedirects(resp, reverse("requests_app:detail", args=[self.req.pk]))
        review = Review.objects.get()
        self.assertEqual((review.rating, review.comment, review.client, review.provider), (4, "Bon travail", self.user, self.provider))
        self.provider.refresh_from_db()
        self.assertEqual((float(self.provider.rating_avg), self.provider.reviews_count), (4.0, 1))
        self.assertTrue(Notification.objects.filter(user=self.provider.user, type="REVIEW").exists())

    def test_comment_is_optional_but_rating_is_required(self):
        self.assertEqual(self.client.post(self.url, {"rating": 5}).status_code, 302)
        Review.objects.all().delete()
        resp = self.client.post(self.url, {"comment": "sans note"})
        self.assertContains(resp, "Choisissez une note")
        self.assertFalse(Review.objects.exists())

    def test_rating_out_of_range_rejected(self):
        for bad in ("0", "6", "abc", "-1"):
            self.client.post(self.url, {"rating": bad})
        self.assertFalse(Review.objects.exists())

    def test_only_on_finished_requests(self):
        for st in (S.SENT, S.VIEWED, S.QUOTED, S.ACCEPTED, S.IN_PROGRESS, S.CANCELLED, S.REFUSED):
            req = make_request(self.user, self.provider, st)
            self.client.post(reverse("reviews:create", args=[req.pk]), {"rating": 5})
            self.assertFalse(Review.objects.filter(request=req).exists(), st)

    def test_one_review_per_request(self):
        self.client.post(self.url, {"rating": 5})
        resp = self.client.post(self.url, {"rating": 1})
        self.assertRedirects(resp, reverse("requests_app:detail", args=[self.req.pk]))
        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(Review.objects.get().rating, 5)

    def test_cannot_review_someone_elses_request(self):
        self.client.force_login(make_user())
        self.assertEqual(self.client.post(self.url, {"rating": 5}).status_code, 404)
        self.assertFalse(Review.objects.exists())

    def test_edit_within_48h_updates_rating(self):
        self.client.post(self.url, {"rating": 5})
        review = Review.objects.get()
        edit = reverse("reviews:edit", args=[review.pk])
        self.assertEqual(self.client.get(edit).status_code, 200)
        self.client.post(edit, {"rating": 2, "comment": "Finalement moyen"})
        review.refresh_from_db()
        self.provider.refresh_from_db()
        self.assertEqual((review.rating, review.comment), (2, "Finalement moyen"))
        self.assertEqual(float(self.provider.rating_avg), 2.0)

    def test_edit_refused_after_48h(self):
        self.client.post(self.url, {"rating": 5})
        review = Review.objects.get()
        Review.objects.filter(pk=review.pk).update(created_at=timezone.now() - timedelta(hours=49))
        edit = reverse("reviews:edit", args=[review.pk])
        self.assertRedirects(self.client.post(edit, {"rating": 1}), reverse("requests_app:detail", args=[self.req.pk]))
        review.refresh_from_db()
        self.assertEqual(review.rating, 5)

    def test_moderated_review_cannot_be_edited(self):
        self.client.post(self.url, {"rating": 5})
        Review.objects.update(status=Review.Status.HIDDEN)
        self.client.post(reverse("reviews:edit", args=[Review.objects.get().pk]), {"rating": 1})
        self.assertEqual(Review.objects.get().rating, 5)

    def test_cannot_edit_others_review(self):
        self.client.post(self.url, {"rating": 5})
        self.client.force_login(make_user())
        self.assertEqual(self.client.post(reverse("reviews:edit", args=[Review.objects.get().pk]), {"rating": 1}).status_code, 404)

    def test_provider_role_cannot_review(self):
        self.client.force_login(self.provider.user)
        self.assertEqual(self.client.post(self.url, {"rating": 5}).status_code, 302)
        self.assertFalse(Review.objects.exists())


class ReportTests(TestCase):
    def setUp(self):
        self.cat = make_catalog()
        self.provider = make_provider(self.cat)
        self.user = make_user()
        self.client.force_login(self.user)

    def test_report_provider(self):
        url = reverse("reviews:report", args=["provider", self.provider.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        resp = self.client.post(url, {"reason": "fake", "details": "Photos volées"})
        self.assertRedirects(resp, self.provider.get_absolute_url(), fetch_redirect_response=False)
        report = Report.objects.get()
        self.assertEqual((report.reporter, report.target_type, report.target_id, report.status), (self.user, "PROVIDER", self.provider.pk, "PENDING"))
        self.assertEqual(report.reason, "Faux profil ou faux avis")

    def test_same_pending_report_not_duplicated(self):
        url = reverse("reviews:report", args=["provider", self.provider.pk])
        self.client.post(url, {"reason": "spam"})
        self.client.post(url, {"reason": "spam"})
        self.assertEqual(Report.objects.count(), 1)

    def test_unknown_reason_rejected(self):
        self.client.post(reverse("reviews:report", args=["provider", self.provider.pk]), {"reason": "<script>"})
        self.assertFalse(Report.objects.exists())

    def test_report_review_but_not_own_or_hidden(self):
        author = make_user()
        req = make_request(author, self.provider, S.DONE)
        review = Review.objects.create(request=req, client=author, provider=self.provider, rating=1, comment="Nul")
        url = reverse("reviews:report", args=["review", review.pk])
        self.client.post(url, {"reason": "abuse"})
        self.assertEqual(Report.objects.get().target_type, "REVIEW")
        self.client.force_login(author)
        self.assertEqual(self.client.get(url).status_code, 404)
        review.status = Review.Status.HIDDEN
        review.save()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_cannot_report_self_non_public_or_unknown_kind(self):
        self.client.force_login(self.provider.user)
        self.assertEqual(self.client.get(reverse("reviews:report", args=["provider", self.provider.pk])).status_code, 404)
        self.client.force_login(self.user)
        hidden = make_provider(self.cat, ProviderProfile.Status.PENDING)
        self.assertEqual(self.client.get(reverse("reviews:report", args=["provider", hidden.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("reviews:report", args=["conversation", 1])).status_code, 404)

    def test_anonymous_redirected_to_login(self):
        self.client.logout()
        resp = self.client.get(reverse("reviews:report", args=["provider", self.provider.pk]))
        self.assertIn(reverse("accounts:login"), resp["Location"])
