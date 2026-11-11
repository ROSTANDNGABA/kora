"""Fabriques minimales pour les tests."""
from apps.accounts.models import User
from apps.catalog.models import Category, CategoryField, City, Subcategory
from apps.providers.models import ProviderProfile

_counter = {"n": 0}


def make_catalog():
    city = City.objects.create(name="Douala", slug="douala")
    plomberie = Category.objects.create(name="Plomberie", slug="plomberie")
    couture = Category.objects.create(name="Couture", slug="couture")
    plombier = Subcategory.objects.create(category=plomberie, name="Plombier", slug="plombier")
    couturier = Subcategory.objects.create(category=couture, name="Couturier", slug="couturier")
    CategoryField.objects.create(category=plomberie, label="Urgence 24/7", key="urgence", field_type="BOOLEAN")
    return {"city": city, "plomberie": plomberie, "couture": couture, "plombier": plombier, "couturier": couturier}


def make_user(role=User.Role.CLIENT, email=None, password="pass12345", **kw):
    _counter["n"] += 1
    email = email or f"user{_counter['n']}@test.cm"
    if role == User.Role.ADMIN:
        kw.setdefault("is_staff", True)
    return User.objects.create_user(email, password, role=role, **kw)


def make_provider(cat, status=ProviderProfile.Status.ACTIVE, **kw):
    user = make_user(User.Role.PROVIDER)
    profile = ProviderProfile.objects.create(
        user=user, business_name=kw.pop("business_name", f"Pro {user.pk}"), category=cat["plomberie"], city=cat["city"],
        whatsapp="699000000", status=status, **kw,
    )
    return profile


def make_request(client, provider, status=None, **kw):
    from apps.requests_app.models import ServiceRequest

    return ServiceRequest.objects.create(
        client=client, provider=provider, description=kw.pop("description", "Besoin d'une intervention rapide chez moi"),
        city=kw.pop("city", provider.city), status=status or ServiceRequest.Status.SENT, **kw,
    )


def make_quote(req, amount=15000, **kw):
    from apps.requests_app.models import Quote

    return Quote.objects.create(request=req, amount=amount, **kw)
