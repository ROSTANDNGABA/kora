from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.core.tests.factories import make_catalog, make_provider, make_user
from apps.requests_app.models import ServiceRequest
from apps.reviews.models import Review


class RatingTests(TestCase):
    def setUp(self):
        self.cat = make_catalog()
        self.provider = make_provider(self.cat)

    def _review(self, rating, status=Review.Status.VISIBLE):
        client = make_user()
        req = ServiceRequest.objects.create(
            client=client, provider=self.provider, description="x", city=self.cat["city"], status=ServiceRequest.Status.DONE,
        )
        return Review.objects.create(request=req, client=client, provider=self.provider, rating=rating, status=status)

    def refreshed(self):
        self.provider.refresh_from_db()
        return self.provider

    def test_average_and_count_follow_reviews(self):
        self._review(5)
        self._review(4)
        self._review(4)
        p = self.refreshed()
        self.assertEqual(p.reviews_count, 3)
        self.assertEqual(p.rating_avg, Decimal("4.33"))

    def test_hidden_reviews_are_excluded(self):
        self._review(5)
        low = self._review(1)
        self.assertEqual(self.refreshed().rating_avg, Decimal("3.00"))
        low.status = Review.Status.HIDDEN
        low.save()
        p = self.refreshed()
        self.assertEqual((p.rating_avg, p.reviews_count), (Decimal("5.00"), 1))
        low.status = Review.Status.VISIBLE
        low.save()
        self.assertEqual(self.refreshed().rating_avg, Decimal("3.00"))

    def test_deleting_review_recomputes(self):
        r1, r2 = self._review(5), self._review(3)
        r2.delete()
        self.assertEqual(self.refreshed().rating_avg, Decimal("5.00"))
        r1.delete()
        p = self.refreshed()
        self.assertEqual((p.rating_avg, p.reviews_count), (Decimal("0.00"), 0))

    def test_one_review_per_request(self):
        review = self._review(5)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Review.objects.create(request=review.request, client=review.client, provider=self.provider, rating=3)

    def test_edit_window_is_48_hours(self):
        review = self._review(4)
        self.assertTrue(review.can_be_edited)
        Review.objects.filter(pk=review.pk).update(created_at=timezone.now() - timezone.timedelta(hours=49))
        review.refresh_from_db()
        self.assertFalse(review.can_be_edited)
