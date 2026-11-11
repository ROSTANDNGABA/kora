"""Génère des données de démonstration réalistes : python manage.py seed_demo [--reset]."""
import random
from datetime import time, timedelta

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import ClientProfile, User
from apps.catalog.models import Category, CategoryField, City, Neighborhood, Subcategory
from apps.cms.models import FAQ, Banner, StaticPage
from apps.dashboard_admin.models import AuditLog
from apps.favorites.models import Favorite, SavedSearch
from apps.messaging.models import Conversation, Message
from apps.notifications.models import Notification
from apps.providers.models import Availability, ProviderDailyStat, ProviderFieldValue, ProviderProfile, Service, Verification
from apps.requests_app.models import Quote, ServiceRequest
from apps.reviews.models import Report, Review
from apps.reviews.services import recompute_provider_rating

from . import _seed_data as D

DEMO_PASSWORD = "Kora2026!"
S = ServiceRequest.Status


class Command(BaseCommand):
    help = "Crée catégories, villes, ~40 prestataires, clients, demandes, avis, conversations et 3 comptes de démo."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Supprime les données de démo existantes avant de régénérer (développement uniquement).")

    @transaction.atomic
    def handle(self, *args, **opts):
        if User.objects.filter(email="admin@kora.cm").exists():
            if not opts["reset"]:
                raise CommandError("Les données de démo existent déjà. Relancez avec --reset pour les régénérer.")
            self._wipe()
        self.rng = random.Random(2026)
        self.now = timezone.now()
        self.pwd = make_password(DEMO_PASSWORD)  # un seul hachage réutilisé : le seed reste rapide

        cats, cities = self._catalog()
        admin = self._admin()
        clients = self._clients(cities)
        providers = self._providers(cats, cities)
        self._requests_and_reviews(providers, clients)
        self._conversations(providers, clients)
        self._extras(admin, providers, clients)
        for p in ProviderProfile.objects.all():
            recompute_provider_rating(p)

        self.stdout.write(self.style.SUCCESS(
            f"Données de démo créées : {len(cats)} catégories, {len(cities)} villes, {len(providers)} prestataires, "
            f"{len(clients)} clients, {ServiceRequest.objects.count()} demandes, {Review.objects.count()} avis."
        ))
        self.stdout.write(f"Comptes : admin@kora.cm / moderateur@kora.cm / support@kora.cm / prestataire@kora.cm / client@kora.cm — mot de passe : {DEMO_PASSWORD}")

    # --- utilitaires --------------------------------------------------------
    def _ago(self, days_max=90, days_min=0):
        return self.now - timedelta(days=self.rng.uniform(days_min, days_max), minutes=self.rng.randint(0, 600))

    def _wipe(self):
        User.objects.filter(email__endswith="kora.cm").delete()  # cascade : profils, demandes, avis, messages…
        for model in (AuditLog, Banner, StaticPage, FAQ, Category, Neighborhood, City):
            model.objects.all().delete()
        self.stdout.write("Anciennes données de démo supprimées.")

    def _user(self, email, first, last, role, phone=None, **extra):
        return User(
            email=email, first_name=first, last_name=last, role=role, phone=phone, password=self.pwd,
            email_verified=True, phone_verified=bool(phone), date_joined=self._ago(180, 1), **extra,
        )

    # --- catalogue ----------------------------------------------------------
    def _catalog(self):
        cats = []
        for order, c in enumerate(D.CATEGORIES):
            cat = Category.objects.create(
                name=c["name"], slug=c["slug"], icon=c["icon"], color=c["color"], description=c["description"], order=order,
            )
            Subcategory.objects.bulk_create(
                [Subcategory(category=cat, name=n, slug=slugify(n), order=i) for i, n in enumerate(c["subs"])]
            )
            CategoryField.objects.bulk_create(
                [CategoryField(category=cat, label=l, key=k, field_type=t, choices=ch, order=i) for i, (l, k, t, ch) in enumerate(c["fields"])]
            )
            cats.append(cat)
        cities = []
        for order, (name, region, hoods) in enumerate(D.CITIES):
            city = City.objects.create(name=name, slug=slugify(name), region=region, order=order)
            Neighborhood.objects.bulk_create([Neighborhood(city=city, name=h) for h in hoods])
            cities.append(city)
        return cats, cities

    def _admin(self):
        admin = self._user("admin@kora.cm", "Admin", "Kora", User.Role.ADMIN, is_staff=True, is_superuser=True)
        admin.save()
        return admin

    # --- clients ------------------------------------------------------------
    def _clients(self, cities):
        rng = self.rng
        people = [("client@kora.cm", "Aïcha", "Ngono")] + [
            (f"{slugify(f)}.{slugify(l)}{i}@demo.kora.cm", f, l)
            for i, (f, l) in enumerate(
                zip(rng.sample(D.FIRST_F + D.FIRST_M, 11), rng.sample(D.LAST, 11)), start=1
            )
        ]
        users = [self._user(e, f, l, User.Role.CLIENT, phone=f"+23767{i:07d}") for i, (e, f, l) in enumerate(people)]
        User.objects.bulk_create(users)
        users = list(User.objects.filter(role=User.Role.CLIENT).order_by("id"))
        ClientProfile.objects.bulk_create([
            ClientProfile(user=u, city=rng.choices(cities, D.CITY_WEIGHTS)[0]) for u in users
        ])
        return users

    # --- prestataires -------------------------------------------------------
    def _providers(self, cats, cities):
        rng = self.rng
        pending, suspended, rejected = {3, 10, 17, 26, 33}, {21}, {38}
        providers = []
        for ci, cat in enumerate(cats):
            subs = list(cat.subcategories.all())
            for k in range(4):
                idx = ci * 4 + k
                is_demo = cat.slug == "plomberie" and k == 0
                city = cities[1] if is_demo else rng.choices(cities, D.CITY_WEIGHTS)[0]
                english = city.name in D.ENGLISH_CITIES
                female = rng.random() < (0.7 if cat.slug in ("couture-stylisme", "coiffure-esthetique", "cuisine-patisserie") else 0.2)
                first = rng.choice(D.FIRST_F if female else D.FIRST_M)
                last = rng.choice(D.LAST_EN if english else D.LAST)
                if is_demo:
                    first, last, email = "Paul", "Tchoumi", "prestataire@kora.cm"
                else:
                    email = f"{slugify(first)}.{slugify(last)}{idx}@demo.kora.cm"
                phone = f"+23769{idx:07d}"
                user = self._user(email, first, last, User.Role.PROVIDER, phone=phone)
                user.save()

                status = ProviderProfile.Status.ACTIVE
                reason = ""
                if idx in pending:
                    status = ProviderProfile.Status.PENDING
                elif idx in suspended:
                    status, reason = ProviderProfile.Status.SUSPENDED, "Plusieurs signalements de clients en cours d'examen."
                elif idx in rejected:
                    status, reason = ProviderProfile.Status.REJECTED, "Informations du profil incomplètes ou non vérifiables."
                active = status == ProviderProfile.Status.ACTIVE
                if is_demo:
                    active, status = True, ProviderProfile.Status.ACTIVE

                form = rng.choice(D.BUSINESS_FORMS[cat.slug])
                name = form.format(L=last, F=first)
                profile = ProviderProfile.objects.create(
                    user=user, business_name=name, category=cat, city=city, whatsapp=phone,
                    description=D.DESCRIPTIONS[cat.slug], status=status, status_reason=reason,
                    activity_type=rng.choice(ProviderProfile.ActivityType.values),
                    is_verified=active and (is_demo or idx % 5 in (0, 2)),
                    is_featured=active and (is_demo or idx % 5 == 0),
                    home_service=rng.random() < 0.5,
                    views_count=rng.randint(40, 1800) if active else 0,
                    whatsapp_clicks=rng.randint(5, 260) if active else 0,
                )
                profile.subcategories.set(rng.sample(subs, k=min(len(subs), rng.randint(1, 2))))
                hoods = list(city.neighborhoods.all())
                if hoods:
                    profile.neighborhoods.set(rng.sample(hoods, k=min(len(hoods), rng.randint(1, 3))))
                self._provider_details(profile, cat)
                providers.append(profile)
        return providers

    def _provider_details(self, profile, cat):
        rng = self.rng
        Service.objects.bulk_create([
            Service(
                provider=profile, title=title, price_type=ptype,
                amount=None if ptype == "QUOTE" else self._round(rng.randint(lo, hi)),
                duration_minutes=dur or None,
                description="Prestation réalisée avec soin, devis détaillé sur demande.",
            )
            for title, ptype, lo, hi, dur in rng.sample(D.SERVICES[cat.slug], k=rng.randint(2, 3))
        ])
        values = []
        for f in cat.fields.all():
            if f.field_type == "TEXT":
                value = rng.choice(D.FIELD_TEXT.get(f.key, ["Sur demande"]))
            elif f.field_type == "NUMBER":
                value = str(rng.randint(2, 30))
            elif f.field_type == "BOOLEAN":
                value = rng.choice(["true", "false"])
            else:
                value = rng.choice(f.choice_list)
            values.append(ProviderFieldValue(provider=profile, field=f, value=value))
        ProviderFieldValue.objects.bulk_create(values)
        saturday_off = rng.random() < 0.25
        Availability.objects.bulk_create([
            Availability(provider=profile, weekday=d, opens_at=time(8, 0), closes_at=time(18, 0))
            for d in range(5)
        ] + [
            Availability(provider=profile, weekday=5, opens_at=time(9, 0), closes_at=time(15, 0), is_closed=saturday_off),
            Availability(provider=profile, weekday=6, is_closed=True),
        ])

    @staticmethod
    def _round(amount, step=500):
        return max(step, round(amount / step) * step)

    # --- demandes, devis, avis ---------------------------------------------
    def _requests_and_reviews(self, providers, clients):
        rng = self.rng
        active = [p for p in providers if p.status == ProviderProfile.Status.ACTIVE]
        demo_client = next(c for c in clients if c.email == "client@kora.cm")
        demo_provider = next(p for p in providers if p.user.email == "prestataire@kora.cm")
        others = [c for c in clients if c != demo_client]

        plan = []  # (client, provider, status)
        for p in active:  # prestations terminées : alimentent les avis
            for _ in range(rng.randint(1, 4)):
                plan.append((rng.choice(others), p, S.DONE))
        for st in S.values:  # le prestataire de démo reçoit une demande à chaque statut
            plan.append((demo_client if st in (S.SENT, S.QUOTED, S.ACCEPTED, S.IN_PROGRESS, S.DONE) else rng.choice(others), demo_provider, st))
        for _ in range(35):  # demandes variées sur les autres prestataires
            st = rng.choice([S.SENT, S.VIEWED, S.QUOTED, S.ACCEPTED, S.IN_PROGRESS, S.CANCELLED, S.REFUSED])
            plan.append((rng.choice(clients), rng.choice(active), st))
        for p in rng.sample(active, 3):  # le client de démo a aussi des prestations terminées à noter
            plan.append((demo_client, p, S.DONE))

        reviews, replies = [], 0
        for client, provider, status in plan:
            created = self._ago(120, 2)
            req = ServiceRequest.objects.create(
                client=client, provider=provider, description=D.NEEDS[provider.category.slug], city=provider.city,
                address=(rng.choice(list(provider.neighborhoods.all())).name if provider.neighborhoods.exists() else ""),
                desired_date=(created + timedelta(days=rng.randint(3, 20))).date(),
                budget=self._round(rng.randint(10000, 200000)) if rng.random() < 0.6 else None,
                status=status,
                refusal_reason="Je ne suis pas disponible sur cette période." if status == S.REFUSED else "",
                completed_at=created + timedelta(days=5) if status == S.DONE else None,
            )
            ServiceRequest.objects.filter(pk=req.pk).update(created_at=created)
            if status in (S.QUOTED, S.ACCEPTED, S.IN_PROGRESS, S.DONE):
                Quote.objects.create(
                    request=req, amount=self._round(rng.randint(8000, 180000)), delay_days=rng.randint(1, 14),
                    message="Voici mon devis pour votre demande. Je reste disponible pour toute question.",
                    valid_until=(self.now + timedelta(days=15)).date(),
                    status=Quote.Status.PENDING if status == S.QUOTED else Quote.Status.ACCEPTED,
                )
            if status == S.DONE:
                # Les prestations terminées du client de démo chez d'autres prestataires restent à noter.
                if client == demo_client and provider != demo_provider:
                    continue
                rating = rng.choices([5, 4, 3, 2, 1], [50, 30, 12, 5, 3])[0]
                review = Review(
                    request=req, client=client, provider=provider, rating=rating, comment=rng.choice(D.REVIEWS[rating]),
                )
                if rating >= 4 and rng.random() < 0.4:
                    review.provider_reply, review.replied_at = rng.choice(D.REPLIES), created + timedelta(days=7)
                    replies += 1
                reviews.append(review)
        Review.objects.bulk_create(reviews)
        # Dates réalistes, puis deux avis masqués par la modération (exclus de la note moyenne).
        for r in Review.objects.select_related("request"):
            Review.objects.filter(pk=r.pk).update(created_at=r.request.completed_at or self.now)
        for r in rng.sample(list(Review.objects.filter(rating__lte=3)), k=min(2, Review.objects.filter(rating__lte=3).count())):
            Review.objects.filter(pk=r.pk).update(status=Review.Status.HIDDEN)

    # --- messagerie ---------------------------------------------------------
    def _conversations(self, providers, clients):
        rng = self.rng
        active = [p for p in providers if p.status == ProviderProfile.Status.ACTIVE]
        demo_client = next(c for c in clients if c.email == "client@kora.cm")
        demo_provider = next(p for p in providers if p.user.email == "prestataire@kora.cm")
        pairs = [(demo_client, demo_provider)] + [(rng.choice(clients), rng.choice(active)) for _ in range(14)]
        seen = set()
        for client, provider in pairs:
            if (client.pk, provider.pk) in seen:
                continue
            seen.add((client.pk, provider.pk))
            start = self._ago(20, 1)
            conv = Conversation.objects.create(client=client, provider=provider)
            last = start
            msgs = D.CHAT[: rng.randint(3, 5)] if (client, provider) != (demo_client, demo_provider) else D.CHAT
            for n, (who, text) in enumerate(msgs):
                last = start + timedelta(minutes=17 * n)
                sender = client if who == "client" else provider.user
                m = Message.objects.create(conversation=conv, sender=sender, body=text, read_at=last + timedelta(minutes=3))
                Message.objects.filter(pk=m.pk).update(created_at=last)
            if (client, provider) == (demo_client, demo_provider):  # dernier message du client : non lu
                newest = conv.messages.order_by("-created_at").first()
                Message.objects.filter(pk=newest.pk).update(read_at=None)
            Conversation.objects.filter(pk=conv.pk).update(updated_at=last)

    # --- favoris, notifications, contenu, signalements, audit --------------
    def _extras(self, admin, providers, clients):
        rng = self.rng
        active = [p for p in providers if p.status == ProviderProfile.Status.ACTIVE]
        demo_client = next(c for c in clients if c.email == "client@kora.cm")
        demo_user = User.objects.get(email="prestataire@kora.cm")

        for p in rng.sample(active, 4):
            Favorite.objects.get_or_create(user=demo_client, provider=p)
        SavedSearch.objects.bulk_create([
            SavedSearch(user=demo_client, label="Plombier à Douala", query_string="q=plombier&ville=douala"),
            SavedSearch(user=demo_client, label="Couturière à Yaoundé", query_string="q=couturiere&ville=yaounde"),
        ])
        Notification.objects.bulk_create([
            Notification(user=demo_user, type="REQUEST", title="Nouvelle demande de devis", body="Aïcha Ngono vous a envoyé une demande."),
            Notification(user=demo_user, type="REVIEW", title="Nouvel avis reçu", body="Un client a laissé un avis sur votre profil."),
            Notification(user=demo_user, type="ACCOUNT", title="Profil validé", body="Votre profil est désormais visible sur Kora.", is_read=True),
            Notification(user=demo_client, type="REQUEST", title="Devis reçu", body="Un prestataire a répondu à votre demande."),
            Notification(user=demo_client, type="MESSAGE", title="Nouveau message", body="Vous avez un nouveau message."),
        ])

        Banner.objects.bulk_create([
            Banner(title="Le savoir-faire camerounais, à portée de main.", subtitle="Trouvez l'artisan qu'il vous faut, près de chez vous.", link_url="/", link_label="Découvrir", order=0),
            Banner(title="Vous êtes artisan ?", subtitle="Gagnez en visibilité et recevez des demandes.", link_url="/compte/inscription/artisan/", link_label="S'inscrire", order=1),
        ])
        StaticPage.objects.bulk_create([StaticPage(slug=s, title=t, body=b) for s, t, b in D.STATIC_PAGES])
        FAQ.objects.bulk_create([FAQ(question=q, answer=a, order=i) for i, (q, a) in enumerate(D.FAQ)])

        review = Review.objects.exclude(client=demo_client).first()
        Report.objects.bulk_create([
            Report(reporter=demo_client, target_type="PROVIDER", target_id=active[0].pk, reason="Informations trompeuses", details="Les tarifs annoncés ne correspondent pas à ceux demandés."),
            Report(reporter=demo_user, target_type="REVIEW", target_id=review.pk, reason="Avis abusif", details="Cet avis ne concerne pas une prestation réelle.", status=Report.Status.RESOLVED, handled_by=admin, handled_at=self.now),
        ])
        self._stats_and_team(active, demo_user)
        AuditLog.objects.bulk_create([
            AuditLog(actor=admin, action="provider.approve", entity_type="ProviderProfile", entity_id=str(active[0].pk), detail={"status": ["PENDING", "ACTIVE"]}, ip_address="127.0.0.1"),
            AuditLog(actor=admin, action="provider.verify", entity_type="ProviderProfile", entity_id=str(active[1].pk), detail={"is_verified": [False, True]}, ip_address="127.0.0.1"),
        ])

    def _stats_and_team(self, active, demo_user):
        """Statistiques journalières sur 90 jours, dossier de vérification en attente, membres d'équipe de démo."""
        from django.contrib.auth.models import Group

        rng = self.rng
        today = timezone.localdate()
        rows = []
        for p in active:
            base = rng.randint(3, 25) if p.user_id != demo_user.pk else 14
            for i in range(90):
                views = max(0, int(rng.gauss(base, base / 3)))
                rows.append(ProviderDailyStat(provider=p, date=today - timedelta(days=i), views=views, whatsapp_clicks=int(views * rng.uniform(0.05, 0.3))))
        ProviderDailyStat.objects.bulk_create(rows, batch_size=1000)
        for p in ProviderProfile.objects.all():  # inscriptions étalées sur trois mois pour des courbes lisibles
            ProviderProfile.objects.filter(pk=p.pk).update(created_at=self._ago(100, 1))
        pending = [p for p in active if not p.is_verified and p.user_id != demo_user.pk][:2]
        for p in pending:
            v = Verification(provider=p)
            v.id_document.save("cni-demo.pdf", ContentFile(b"%PDF-1.4 piece de demonstration"), save=False)
            v.save()
        for email, first, last, group in (("moderateur@kora.cm", "Mireille", "Tchoua", "Modérateur"), ("support@kora.cm", "Serge", "Ondoa", "Support")):
            member = self._user(email, first, last, User.Role.ADMIN, is_staff=True)
            member.save()
            g = Group.objects.filter(name=group).first()
            if g:
                member.groups.add(g)
