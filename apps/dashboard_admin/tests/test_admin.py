import shutil
import tempfile

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.catalog.models import Category, CategoryField, City
from apps.cms.models import FAQ, Banner, StaticPage
from apps.core.tests.factories import make_catalog, make_provider, make_request, make_user
from apps.dashboard_admin.models import Announcement, AuditLog
from apps.dashboard_admin.permissions import GROUPS, MODULES, can_access_module, ensure_groups
from apps.notifications.models import Notification
from apps.providers.models import ProviderProfile, Verification
from apps.requests_app.models import ServiceRequest
from apps.reviews.models import Report, Review

P = ProviderProfile.Status
PRIVATE = tempfile.mkdtemp()


def url(name, *args):
    return reverse(f"dashboard_admin:{name}", args=args)


@override_settings(PRIVATE_MEDIA_ROOT=PRIVATE, MEDIA_ROOT=tempfile.mkdtemp())
class AdminBase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(PRIVATE, ignore_errors=True)

    def setUp(self):
        ensure_groups()
        self.cat = make_catalog()
        self.admin = make_user(User.Role.ADMIN, is_superuser=True)
        self.client.force_login(self.admin)
        self.pro = make_provider(self.cat, status=P.PENDING)
        self.customer = make_user()

    def member(self, group):
        m = make_user(User.Role.ADMIN)
        m.groups.add(Group.objects.get(name=group))
        return m

    def last_audit(self, action):
        return AuditLog.objects.filter(action=action).first()


class AccessTests(AdminBase):
    PAGES = ["home", "clients", "providers", "verifications", "categories", "cities", "requests", "reviews", "reports", "content", "communication", "team", "audit", "settings"]

    def test_all_pages_render_for_superuser(self):
        for name in self.PAGES + ["team_new", "category_new", "city_new", "banner_new", "page_new", "faq_new", "field_new", "subcategory_new", "neighborhood_new"]:
            with self.subTest(name):
                self.assertEqual(self.client.get(url(name)).status_code, 200)
        self.assertEqual(self.client.get(url("search"), {"q": "pro"}).status_code, 200)

    def test_anonymous_redirected_to_login(self):
        self.client.logout()
        for name in self.PAGES:
            self.assertEqual(self.client.get(url(name)).status_code, 302, name)

    def test_client_and_provider_forbidden(self):
        for user in (self.customer, self.pro.user):
            self.client.force_login(user)
            for name in ("home", "clients", "audit"):
                self.assertEqual(self.client.get(url(name)).status_code, 302, name)  # renvoyés vers leur propre espace

    def test_moderator_scope(self):
        mod = self.member("Modérateur")
        self.client.force_login(mod)
        for name in ("providers", "reviews", "reports", "content"):
            self.assertEqual(self.client.get(url(name)).status_code, 200, name)
        for name in ("clients", "team", "audit", "settings", "communication", "requests", "categories"):
            self.assertEqual(self.client.get(url(name)).status_code, 403, name)

    def test_support_scope(self):
        self.client.force_login(self.member("Support"))
        self.assertEqual(self.client.get(url("clients")).status_code, 200)
        self.assertEqual(self.client.get(url("providers")).status_code, 403)

    def test_actions_checked_server_side(self):
        self.client.force_login(self.member("Support"))
        r = self.client.post(url("provider_approve", self.pro.pk))
        self.assertEqual(r.status_code, 403)
        self.pro.refresh_from_db()
        self.assertEqual(self.pro.status, P.PENDING)

    def test_sidebar_hides_forbidden_modules(self):
        self.client.force_login(self.member("Modérateur"))
        html = self.client.get(url("home")).content.decode()
        self.assertIn(url("providers"), html)
        self.assertNotIn(url("team"), html)
        self.assertNotIn(url("audit"), html)

    def test_actions_are_post_only(self):
        self.assertEqual(self.client.get(url("provider_approve", self.pro.pk)).status_code, 405)
        self.assertEqual(self.client.get(url("client_delete", self.customer.pk)).status_code, 405)

    def test_groups_created_with_expected_modules(self):
        for name, modules in GROUPS.items():
            g = Group.objects.get(name=name)
            self.assertEqual({p.codename for p in g.permissions.filter(codename__startswith="module_")}, {f"module_{m}" for m in modules})
        self.assertEqual(len(MODULES), 11)

    def test_inactive_admin_has_no_access(self):
        self.assertFalse(can_access_module(User(role="ADMIN", is_active=False, is_superuser=True), "clients"))

    def test_badges_in_sidebar(self):
        html = self.client.get(url("home")).content.decode()
        self.assertIn("rounded-full bg-kora-yellow", html)


class ProviderModerationTests(AdminBase):
    def test_approve_notifies_and_audits(self):
        self.client.post(url("provider_approve", self.pro.pk))
        self.pro.refresh_from_db()
        self.assertEqual(self.pro.status, P.ACTIVE)
        self.assertTrue(Notification.objects.filter(user=self.pro.user, title__icontains="validé").exists())
        entry = self.last_audit("provider.approve")
        self.assertEqual((entry.actor, entry.entity_id), (self.admin, str(self.pro.pk)))
        self.assertEqual(entry.ip_address, "127.0.0.1")

    def test_reject_requires_reason(self):
        self.client.post(url("provider_reject", self.pro.pk), {"reason": ""})
        self.pro.refresh_from_db()
        self.assertEqual(self.pro.status, P.PENDING)
        self.client.post(url("provider_reject", self.pro.pk), {"reason": "Pièces illisibles, merci de réessayer"})
        self.pro.refresh_from_db()
        self.assertEqual((self.pro.status, self.pro.status_reason), (P.REJECTED, "Pièces illisibles, merci de réessayer"))
        self.assertTrue(Notification.objects.filter(user=self.pro.user, body__icontains="illisibles").exists())

    def test_pending_provider_invisible_until_approved(self):
        self.assertFalse(ProviderProfile.objects.public().filter(pk=self.pro.pk).exists())
        self.client.post(url("provider_approve", self.pro.pk))
        self.assertTrue(ProviderProfile.objects.public().filter(pk=self.pro.pk).exists())

    def test_suspend_and_reactivate(self):
        self.pro.status = P.ACTIVE
        self.pro.save()
        self.client.post(url("provider_suspend", self.pro.pk), {"reason": "Plaintes répétées"})
        self.pro.refresh_from_db()
        self.assertEqual(self.pro.status, P.SUSPENDED)
        self.assertFalse(ProviderProfile.objects.public().filter(pk=self.pro.pk).exists())
        self.client.post(url("provider_reactivate", self.pro.pk))
        self.pro.refresh_from_db()
        self.assertEqual(self.pro.status, P.ACTIVE)
        self.assertEqual(AuditLog.objects.filter(action__startswith="provider.").count(), 2)

    def test_invalid_transition_refused(self):
        self.client.post(url("provider_suspend", self.pro.pk), {"reason": "Test de transition"})  # PENDING ne se suspend pas
        self.pro.refresh_from_db()
        self.assertEqual(self.pro.status, P.PENDING)

    def test_verified_and_featured_toggle(self):
        self.pro.status = P.ACTIVE
        self.pro.save()
        self.client.post(url("provider_verified", self.pro.pk))
        self.client.post(url("provider_featured", self.pro.pk))
        self.pro.refresh_from_db()
        self.assertTrue(self.pro.is_verified and self.pro.is_featured)
        self.client.post(url("provider_verified", self.pro.pk))
        self.pro.refresh_from_db()
        self.assertFalse(self.pro.is_verified)

    def test_cannot_feature_inactive_provider(self):
        self.client.post(url("provider_featured", self.pro.pk))
        self.pro.refresh_from_db()
        self.assertFalse(self.pro.is_featured)

    def test_category_change_approve_and_reject(self):
        self.pro.status = P.ACTIVE
        self.pro.pending_category = self.cat["couture"]
        self.pro.save()
        self.pro.subcategories.add(self.cat["plombier"])
        self.client.post(url("category_change_reject", self.pro.pk), {"reason": "Justificatif manquant"})
        self.pro.refresh_from_db()
        self.assertIsNone(self.pro.pending_category)
        self.assertEqual(self.pro.category, self.cat["plomberie"])
        self.pro.pending_category = self.cat["couture"]
        self.pro.save()
        self.client.post(url("category_change_approve", self.pro.pk))
        self.pro.refresh_from_db()
        self.assertEqual(self.pro.category, self.cat["couture"])
        self.assertFalse(self.pro.subcategories.exists())

    def test_edit_provider_audited(self):
        r = self.client.post(url("provider_edit", self.pro.pk), {"business_name": "Nouveau nom", "activity_type": "FREELANCE", "category": self.cat["plomberie"].pk, "city": self.cat["city"].pk, "whatsapp": "699111222", "description": "x"})
        self.assertEqual(r.status_code, 302)
        self.pro.refresh_from_db()
        self.assertEqual(self.pro.business_name, "Nouveau nom")
        self.assertTrue(self.last_audit("provider.update"))

    def test_list_filters_and_csv(self):
        make_provider(self.cat, status=P.ACTIVE, business_name="Zeta")
        r = self.client.get(url("providers"), {"statut": "ACTIVE"})
        self.assertEqual([p.business_name for p in r.context["page_obj"]], ["Zeta"])
        r = self.client.get(url("providers"), {"export": "csv"})
        self.assertEqual(r["Content-Type"], "text/csv; charset=utf-8")
        self.assertTrue(self.last_audit("providers.export"))


class ClientModerationTests(AdminBase):
    def test_suspend_blocks_login_and_notifies(self):
        self.client.post(url("client_suspend", self.customer.pk), {"reason": "Comportement abusif envers un artisan"})
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_active)
        self.assertTrue(Notification.objects.filter(user=self.customer).exists())
        self.client.logout()
        self.assertFalse(self.client.login(email=self.customer.email, password="pass12345"))
        self.client.force_login(self.admin)
        self.client.post(url("client_reactivate", self.customer.pk))
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_active)

    def test_delete_client_audited(self):
        pk = self.customer.pk
        self.client.post(url("client_delete", pk))
        self.assertFalse(User.objects.filter(pk=pk).exists())
        self.assertEqual(self.last_audit("client.delete").detail["id"], pk)

    def test_cannot_delete_non_client_through_client_route(self):
        self.assertEqual(self.client.post(url("client_delete", self.pro.user.pk)).status_code, 404)
        self.assertEqual(self.client.post(url("client_delete", self.admin.pk)).status_code, 404)

    def test_csv_export_neutralises_formulas(self):
        make_user(first_name="=HYPERLINK(\"http://x\")", last_name="Zed")
        body = self.client.get(url("clients"), {"export": "csv"}).content.decode("utf-8")
        self.assertIn("'=HYPERLINK", body)
        self.assertNotIn(";=HYPERLINK", body)

    def test_search_and_sort_whitelist(self):
        r = self.client.get(url("clients"), {"q": self.customer.email, "sort": "password"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.context["page_obj"]), 1)


class VerificationTests(AdminBase):
    def dossier(self):
        v = Verification(provider=self.pro)
        v.id_document.save("cni.pdf", SimpleUploadedFile("cni.pdf", b"%PDF-1.4 x"), save=False)
        v.save()
        return v

    def test_approve_sets_badge(self):
        v = self.dossier()
        self.client.post(url("verification_approve", v.pk))
        v.refresh_from_db()
        self.pro.refresh_from_db()
        self.assertEqual((v.status, v.reviewer), ("APPROVED", self.admin))
        self.assertTrue(self.pro.is_verified)
        self.assertTrue(Notification.objects.filter(user=self.pro.user).exists())

    def test_reject_needs_reason_and_keeps_badge_off(self):
        v = self.dossier()
        self.client.post(url("verification_reject", v.pk), {"reason": ""})
        v.refresh_from_db()
        self.assertEqual(v.status, "PENDING")
        self.client.post(url("verification_reject", v.pk), {"reason": "Photo floue, renvoyez la pièce"})
        v.refresh_from_db()
        self.pro.refresh_from_db()
        self.assertEqual(v.status, "REJECTED")
        self.assertFalse(self.pro.is_verified)

    def test_already_processed_not_reprocessed(self):
        v = self.dossier()
        self.client.post(url("verification_approve", v.pk))
        self.client.post(url("verification_reject", v.pk), {"reason": "Trop tard pour refuser"})
        v.refresh_from_db()
        self.assertEqual(v.status, "APPROVED")

    def test_file_served_only_to_authorised_admin(self):
        v = self.dossier()
        r = self.client.get(url("verification_file", v.pk, "identite"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self.last_audit("verification.view_file"))
        self.client.force_login(self.member("Support"))
        self.assertEqual(self.client.get(url("verification_file", v.pk, "identite")).status_code, 403)
        self.client.force_login(self.pro.user)
        self.assertEqual(self.client.get(url("verification_file", v.pk, "identite")).status_code, 302)
        self.client.logout()
        self.assertEqual(self.client.get(url("verification_file", v.pk, "identite")).status_code, 302)

    def test_document_not_under_public_media(self):
        v = self.dossier()
        self.assertTrue(v.id_document.path.startswith(PRIVATE))
        with self.assertRaises(Exception):
            v.id_document.url


class CatalogTests(AdminBase):
    def test_category_crud_with_auto_slug(self):
        r = self.client.post(url("category_new"), {"name": "Menuiserie", "slug": "", "icon": "hammer", "color": "#F36F21", "order": 3, "is_active": "on"})
        self.assertEqual(r.status_code, 302)
        cat = Category.objects.get(name="Menuiserie")
        self.assertEqual(cat.slug, "menuiserie")
        self.client.post(url("category_edit", cat.pk), {"name": "Menuiserie bois", "slug": "menuiserie", "icon": "hammer", "color": "#4A1F0E", "order": 3, "is_active": "on"})
        cat.refresh_from_db()
        self.assertEqual(cat.name, "Menuiserie bois")
        self.assertTrue(self.last_audit("category.update"))

    def test_invalid_color_rejected(self):
        r = self.client.post(url("category_new"), {"name": "X", "icon": "hammer", "color": "red", "order": 0})
        self.assertEqual(r.status_code, 200)

    def test_cannot_delete_category_in_use(self):
        from django.contrib.messages import get_messages

        r = self.client.post(url("category_delete", self.cat["plomberie"].pk), follow=True)
        self.assertTrue(Category.objects.filter(pk=self.cat["plomberie"].pk).exists())
        self.assertIn("encore utilisé", " ".join(str(m) for m in get_messages(r.wsgi_request)))

    def test_delete_unused_category(self):
        unused = Category.objects.create(name="Vide", slug="vide")
        self.client.post(url("category_delete", unused.pk))
        self.assertFalse(Category.objects.filter(pk=unused.pk).exists())
        self.assertTrue(self.last_audit("category.delete"))

    def test_toggle_category(self):
        self.client.post(url("category_toggle", self.cat["couture"].pk))
        self.cat["couture"].refresh_from_db()
        self.assertFalse(self.cat["couture"].is_active)

    def test_field_builder(self):
        base = {"category": self.cat["couture"].pk, "label": "Type de tissu", "key": "", "field_type": "CHOICE", "choices": "Wax\nBazin", "order": 1, "is_active": "on"}
        r = self.client.post(url("field_new"), base)
        self.assertRedirects(r, url("category_fields", self.cat["couture"].pk), fetch_redirect_response=False)
        f = CategoryField.objects.get(label="Type de tissu")
        self.assertEqual((f.key, f.choice_list), ("type_de_tissu", ["Wax", "Bazin"]))

    def test_choice_field_needs_two_options(self):
        r = self.client.post(url("field_new"), {"category": self.cat["couture"].pk, "label": "Taille", "field_type": "CHOICE", "choices": "Unique", "order": 0})
        self.assertEqual(r.status_code, 200)

    def test_duplicate_field_key_rejected(self):
        r = self.client.post(url("field_new"), {"category": self.cat["plomberie"].pk, "label": "Urgence 24/7", "key": "urgence", "field_type": "BOOLEAN", "order": 0})
        self.assertEqual(r.status_code, 200)

    def test_subcategory_crud(self):
        r = self.client.post(url("subcategory_new"), {"category": self.cat["couture"].pk, "name": "Brodeur", "slug": "", "order": 0, "is_active": "on"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(self.cat["couture"].subcategories.filter(slug="brodeur").exists())

    def test_city_and_neighborhood(self):
        self.client.post(url("city_new"), {"name": "Bafoussam", "slug": "", "region": "Ouest", "order": 5, "is_active": "on"})
        city = City.objects.get(name="Bafoussam")
        r = self.client.post(url("neighborhood_new"), {"city": city.pk, "name": "Tamdja", "is_active": "on"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(city.neighborhoods.count(), 1)
        self.assertEqual(self.client.post(url("city_delete", self.cat["city"].pk)).status_code, 302)
        self.assertTrue(City.objects.filter(pk=self.cat["city"].pk).exists())  # utilisée par un prestataire


class ModerationTests(AdminBase):
    def setUp(self):
        super().setUp()
        self.pro.status = P.ACTIVE
        self.pro.save()
        self.req = make_request(self.customer, self.pro, status=ServiceRequest.Status.DONE)
        self.review = Review.objects.create(request=self.req, client=self.customer, provider=self.pro, rating=1, comment="Nul")

    def test_hide_review_updates_rating_and_notifies(self):
        self.pro.refresh_from_db()
        self.assertEqual(self.pro.reviews_count, 1)
        self.client.post(url("review_hide", self.review.pk), {"reason": "Propos injurieux"})
        self.pro.refresh_from_db()
        self.review.refresh_from_db()
        self.assertEqual((self.review.status, self.pro.reviews_count), ("HIDDEN", 0))
        self.assertTrue(Notification.objects.filter(user=self.customer, type="REVIEW").exists())
        self.client.post(url("review_restore", self.review.pk))
        self.pro.refresh_from_db()
        self.assertEqual(self.pro.reviews_count, 1)

    def test_hide_requires_reason(self):
        self.client.post(url("review_hide", self.review.pk), {"reason": ""})
        self.review.refresh_from_db()
        self.assertEqual(self.review.status, "VISIBLE")

    def test_delete_review(self):
        self.client.post(url("review_delete", self.review.pk), {"reason": "Faux avis avéré"})
        self.assertFalse(Review.objects.exists())
        self.assertTrue(self.last_audit("review.delete"))

    def test_review_filters(self):
        r = self.client.get(url("reviews"), {"filtre": "notes-basses"})
        self.assertEqual(len(r.context["page_obj"]), 1)
        r = self.client.get(url("reviews"), {"filtre": "signales"})
        self.assertEqual(len(r.context["page_obj"]), 0)
        Report.objects.create(reporter=self.pro.user, target_type="REVIEW", target_id=self.review.pk, reason="Abusif")
        r = self.client.get(url("reviews"), {"filtre": "signales"})
        self.assertEqual(len(r.context["page_obj"]), 1)

    def test_report_resolve_hides_review_and_notifies_reporter(self):
        rep = Report.objects.create(reporter=self.pro.user, target_type="REVIEW", target_id=self.review.pk, reason="Abusif")
        self.client.post(url("report_treat", rep.pk), {"decision": "resolve", "note": "Avis retiré, merci", "action": "hide_review"})
        rep.refresh_from_db()
        self.review.refresh_from_db()
        self.assertEqual((rep.status, rep.handled_by, self.review.status), ("RESOLVED", self.admin, "HIDDEN"))
        self.assertTrue(Notification.objects.filter(user=self.pro.user, body__icontains="Avis retiré").exists())

    def test_report_reject_changes_nothing_on_target(self):
        rep = Report.objects.create(reporter=self.customer, target_type="PROVIDER", target_id=self.pro.pk, reason="Doute")
        self.client.post(url("report_treat", rep.pk), {"decision": "reject", "note": "Rien d'anormal constaté", "action": "suspend_provider"})
        rep.refresh_from_db()
        self.pro.refresh_from_db()
        self.assertEqual((rep.status, self.pro.status), ("REJECTED", P.ACTIVE))

    def test_report_suspend_provider(self):
        rep = Report.objects.create(reporter=self.customer, target_type="PROVIDER", target_id=self.pro.pk, reason="Arnaque")
        self.client.post(url("report_treat", rep.pk), {"decision": "resolve", "note": "Suspendu après vérification", "action": "suspend_provider"})
        self.pro.refresh_from_db()
        self.assertEqual(self.pro.status, P.SUSPENDED)

    def test_report_cannot_be_treated_twice(self):
        rep = Report.objects.create(reporter=self.customer, target_type="PROVIDER", target_id=self.pro.pk, reason="x")
        self.client.post(url("report_treat", rep.pk), {"decision": "reject", "note": "Non fondé du tout"})
        self.client.post(url("report_treat", rep.pk), {"decision": "resolve", "note": "Finalement fondé"})
        rep.refresh_from_db()
        self.assertEqual(rep.status, "REJECTED")

    def test_report_note_required(self):
        rep = Report.objects.create(reporter=self.customer, target_type="PROVIDER", target_id=self.pro.pk, reason="x")
        self.client.post(url("report_treat", rep.pk), {"decision": "resolve", "note": ""})
        rep.refresh_from_db()
        self.assertEqual(rep.status, "PENDING")

    def test_report_detail_for_each_target_type(self):
        from apps.messaging.models import Conversation

        conv = Conversation.objects.create(client=self.customer, provider=self.pro)
        for kind, pk in (("PROVIDER", self.pro.pk), ("REVIEW", self.review.pk), ("CONVERSATION", conv.pk), ("REVIEW", 9999)):
            rep = Report.objects.create(reporter=self.customer, target_type=kind, target_id=pk, reason="r")
            self.assertEqual(self.client.get(url("report_detail", rep.pk)).status_code, 200)

    def test_cancel_request_notifies_both(self):
        req = make_request(self.customer, self.pro)
        self.client.post(url("request_cancel", req.pk), {"reason": "Litige non résolu entre les parties"})
        req.refresh_from_db()
        self.assertEqual(req.status, "CANCELLED")
        self.assertTrue(Notification.objects.filter(user=self.customer).exists() and Notification.objects.filter(user=self.pro.user).exists())

    def test_cannot_cancel_finished_request(self):
        self.client.post(url("request_cancel", self.req.pk), {"reason": "Trop tard pour annuler"})
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "DONE")

    def test_mediation_message(self):
        before = Notification.objects.count()
        self.client.post(url("request_mediate", self.req.pk), {"reason": "Merci de vous accorder sur la date"})
        self.assertEqual(Notification.objects.count(), before + 2)

    def test_request_list_filters_and_detail(self):
        r = self.client.get(url("requests"), {"statut": "DONE", "q": str(self.req.pk)})
        self.assertEqual(len(r.context["page_obj"]), 1)
        self.assertEqual(self.client.get(url("request_detail", self.req.pk)).status_code, 200)


class ContentCommunicationTests(AdminBase):
    def test_banner_page_faq_crud(self):
        self.client.post(url("banner_new"), {"title": "Promo", "subtitle": "", "link_url": "/artisans", "link_label": "Voir", "order": 0, "is_active": "on"})
        self.assertTrue(Banner.objects.filter(title="Promo").exists())
        self.client.post(url("page_new"), {"title": "Mentions", "slug": "Mentions Légales", "body": "Texte", "is_published": "on"})
        self.assertTrue(StaticPage.objects.filter(slug="mentions-legales").exists())
        self.client.post(url("faq_new"), {"question": "Comment ?", "answer": "Ainsi.", "order": 0, "is_active": "on"})
        faq = FAQ.objects.get()
        self.client.post(url("faq_toggle", faq.pk))
        faq.refresh_from_db()
        self.assertFalse(faq.is_active)
        self.client.post(url("faq_delete", faq.pk))
        self.assertFalse(FAQ.objects.exists())

    def test_banner_rejects_dangerous_link(self):
        r = self.client.post(url("banner_new"), {"title": "X", "link_url": "javascript:alert(1)", "order": 0})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Banner.objects.exists())
        r = self.client.post(url("banner_new"), {"title": "X", "link_url": "//evil.example", "order": 0})
        self.assertFalse(Banner.objects.exists())

    def test_unfeature(self):
        self.pro.status, self.pro.is_featured = P.ACTIVE, True
        self.pro.save()
        self.client.post(url("unfeature", self.pro.pk))
        self.pro.refresh_from_db()
        self.assertFalse(self.pro.is_featured)

    def test_announcement_reaches_audience_only(self):
        provider = make_provider(self.cat, status=P.ACTIVE)
        suspended = make_user(is_active=False)
        r = self.client.post(url("communication"), {"audience": "CLIENTS", "title": "Maintenance", "body": "Ce soir à 22h", "url": ""})
        self.assertEqual(r.status_code, 302)
        ann = Announcement.objects.get()
        self.assertTrue(Notification.objects.filter(user=self.customer, title="Maintenance").exists())
        self.assertFalse(Notification.objects.filter(user=provider.user, title="Maintenance").exists())
        self.assertFalse(Notification.objects.filter(user=suspended).exists())
        self.assertFalse(Notification.objects.filter(user=self.admin).exists())
        self.assertEqual(ann.recipients_count, User.objects.filter(role="CLIENT", is_active=True).count())
        self.assertEqual(self.last_audit("announcement.send").detail["audience"], "CLIENTS")

    def test_announcement_external_link_rejected(self):
        self.client.post(url("communication"), {"audience": "ALL", "title": "T", "body": "B", "url": "https://phishing.example"})
        self.assertFalse(Announcement.objects.exists())

    def test_targeted_notification(self):
        self.client.post(url("notification_send"), {"email": self.customer.email.upper(), "title": "Bonjour", "body": "Message perso"})
        self.assertTrue(Notification.objects.filter(user=self.customer, title="Bonjour").exists())
        self.client.post(url("notification_send"), {"email": "inconnu@test.cm", "title": "x", "body": "y"})
        self.assertEqual(Notification.objects.filter(title="x").count(), 0)

    def test_notification_text_escaped_for_recipient(self):
        self.client.post(url("notification_send"), {"email": self.customer.email, "title": "<b>Gras</b>", "body": "<script>alert(1)</script>"})
        self.client.force_login(self.customer)
        html = self.client.get(reverse("notifications:list")).content.decode()
        self.assertNotIn("<script>alert(1)</script>", html)


class TeamAuditSettingsTests(AdminBase):
    def test_create_member_with_role(self):
        r = self.client.post(url("team_new"), {"email": "nouveau@kora.cm", "first_name": "Nina", "last_name": "Eto", "password": "Mot-de-passe-2026", "groups": [Group.objects.get(name="Support").pk], "is_active": "on"})
        self.assertEqual(r.status_code, 302)
        m = User.objects.get(email="nouveau@kora.cm")
        self.assertEqual((m.role, m.is_staff, list(m.groups.values_list("name", flat=True))), ("ADMIN", True, ["Support"]))
        self.assertTrue(m.check_password("Mot-de-passe-2026"))
        self.assertNotIn("Mot-de-passe", str(self.last_audit("team.create").detail))
        self.client.force_login(m)
        self.assertEqual(self.client.get(url("clients")).status_code, 200)
        self.assertEqual(self.client.get(url("providers")).status_code, 403)

    def test_weak_password_rejected(self):
        r = self.client.post(url("team_new"), {"email": "x@kora.cm", "first_name": "A", "last_name": "B", "password": "1234567890", "is_active": "on"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(email="x@kora.cm").exists())

    def test_change_roles(self):
        m = self.member("Support")
        self.client.post(url("team_edit", m.pk), {"first_name": "A", "last_name": "B", "groups": [Group.objects.get(name="Modérateur").pk], "is_active": "on"})
        self.assertEqual(list(m.groups.values_list("name", flat=True)), ["Modérateur"])

    def test_cannot_deactivate_self(self):
        self.client.post(url("team_toggle", self.admin.pk))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_non_superuser_cannot_touch_superuser(self):
        lead = make_user(User.Role.ADMIN)
        lead.groups.add(Group.objects.get(name="Administrateur complet"))
        self.client.force_login(lead)
        self.client.post(url("team_toggle", self.admin.pk))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertEqual(self.client.post(url("team_edit", self.admin.pk), {"first_name": "Pirate", "last_name": "X", "is_active": "on"}).status_code, 302)
        self.admin.refresh_from_db()
        self.assertNotEqual(self.admin.first_name, "Pirate")

    def test_audit_filters_and_csv(self):
        self.client.post(url("provider_approve", self.pro.pk))
        r = self.client.get(url("audit"), {"action": "provider.", "acteur": self.admin.pk})
        self.assertEqual(len(r.context["page_obj"]), 1)
        r = self.client.get(url("audit"), {"du": "2999-01-01"})
        self.assertEqual(len(r.context["page_obj"]), 0)
        r = self.client.get(url("audit"), {"du": "pas-une-date", "q": "pas.une.ip"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("provider.approve", self.client.get(url("audit"), {"export": "csv"}).content.decode())

    def test_audit_is_read_only(self):
        self.client.post(url("provider_approve", self.pro.pk))
        entry = AuditLog.objects.first()
        for method in (self.client.post, self.client.get):
            self.assertEqual(method(f"/back-office/audit/{entry.pk}/supprimer/").status_code, 404)

    def test_settings_update_applies_limits(self):
        r = self.client.post(url("settings"), {"site_slogan": "Nouveau slogan", "support_whatsapp": "+237 600 000 000", "contact_email": "a@b.cm", "upload_max_mb": 8, "portfolio_max_items": 12})
        self.assertEqual(r.status_code, 302)
        from apps.core import site_settings

        self.assertEqual(site_settings.upload_limit_mb(), 8)
        self.assertEqual(site_settings.portfolio_limit(), 12)
        self.assertContains(self.client.get(reverse("core:home")), "Nouveau slogan")

    def test_settings_bounds(self):
        r = self.client.post(url("settings"), {"upload_max_mb": 500, "portfolio_max_items": 0, "support_whatsapp": "abc"})
        self.assertEqual(r.status_code, 200)

    def test_dashboard_data_and_csv(self):
        r = self.client.get(url("home"))
        self.assertIn("signups", r.context["chart"])
        body = self.client.get(url("home"), {"export": "csv"}).content.decode("utf-8")
        self.assertIn("Clients", body)

    def test_global_search_respects_permissions(self):
        self.client.force_login(self.member("Support"))
        r = self.client.get(url("search"), {"q": self.pro.business_name[:5]})
        self.assertNotIn("providers", r.context["results"])
        self.assertIn("clients", r.context["results"])
