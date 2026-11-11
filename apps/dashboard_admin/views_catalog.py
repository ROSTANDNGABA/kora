"""Catégories, sous-catégories, champs spécifiques, villes et quartiers."""
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.urls import reverse

from apps.catalog.models import Category, CategoryField, City, Neighborhood, Subcategory

from .forms import CategoryFieldForm, CategoryForm, CityForm, NeighborhoodForm, SubcategoryForm
from .views_base import AdminPage, CrudDeleteView, CrudFormView, ObjectAction, audit, safe_next


class CategoryListView(AdminPage):
    module = "catalog"
    template_name = "dashboard_admin/categories.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = Category.objects.annotate(
            providers_count=Count("providers", distinct=True), fields_count=Count("fields", distinct=True), subs_count=Count("subcategories", distinct=True)
        )
        return ctx


class CategoryFormView(CrudFormView):
    module = "catalog"
    model = Category
    form_class = CategoryForm
    audit_name = "category"
    list_url_name = "dashboard_admin:categories"
    heading_new, heading_edit = "Nouvelle catégorie", "Modifier la catégorie"
    multipart = True


class CategoryDeleteView(CrudDeleteView):
    module = "catalog"
    model = Category
    audit_name = "category"
    list_url_name = "dashboard_admin:categories"


class CategoryFieldsView(AdminPage):
    """Sous-catégories et champs spécifiques d'une catégorie (constructeur de champs)."""

    module = "catalog"
    template_name = "dashboard_admin/category_fields.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cat = get_object_or_404(Category, pk=self.kwargs["pk"])
        ctx.update(category=cat, subcategories=cat.subcategories.all(), fields=cat.fields.all())
        return ctx


class _CategoryChildForm(CrudFormView):
    module = "catalog"
    initial_from_get = ("category",)

    def get_success_url(self):
        cat_id = self.object.category_id if self.object else self.request.GET.get("category") or self.request.POST.get("category")
        return reverse("dashboard_admin:category_fields", args=[cat_id]) if cat_id else reverse("dashboard_admin:categories")


class FieldFormView(_CategoryChildForm):
    model = CategoryField
    form_class = CategoryFieldForm
    audit_name = "category_field"
    heading_new, heading_edit = "Nouveau champ", "Modifier le champ"


class SubcategoryFormView(_CategoryChildForm):
    model = Subcategory
    form_class = SubcategoryForm
    audit_name = "subcategory"
    heading_new, heading_edit = "Nouvelle sous-catégorie", "Modifier la sous-catégorie"


class _ChildDelete(CrudDeleteView):
    module = "catalog"

    def get_redirect(self, request, obj):
        return safe_next(request, reverse("dashboard_admin:category_fields", args=[obj.category_id]))


class FieldDeleteView(_ChildDelete):
    model = CategoryField
    audit_name = "category_field"


class SubcategoryDeleteView(_ChildDelete):
    model = Subcategory
    audit_name = "subcategory"


class ToggleActiveView(ObjectAction):
    """Active ou désactive un élément du catalogue (alternative non destructive à la suppression)."""

    module = "catalog"
    model = None
    audit_name = ""
    back = "dashboard_admin:categories"

    def get_queryset(self):
        return self.model.objects.all()

    def get_redirect(self, request, obj):
        return safe_next(request, reverse(self.back))

    def perform(self, request, obj, reason):
        obj.is_active = not obj.is_active
        obj.save(update_fields=["is_active"])
        audit.log(request, f"{self.audit_name}.{'enable' if obj.is_active else 'disable'}", obj)
        self.success = "Activé." if obj.is_active else "Désactivé."


class CategoryToggleView(ToggleActiveView):
    model, audit_name = Category, "category"


class FieldToggleView(ToggleActiveView):
    model, audit_name = CategoryField, "category_field"


class SubcategoryToggleView(ToggleActiveView):
    model, audit_name = Subcategory, "subcategory"


class CityToggleView(ToggleActiveView):
    model, audit_name, back = City, "city", "dashboard_admin:cities"


class NeighborhoodToggleView(ToggleActiveView):
    model, audit_name, back = Neighborhood, "neighborhood", "dashboard_admin:cities"


# --- Villes et quartiers -----------------------------------------------------
class CityListView(AdminPage):
    module = "catalog"
    template_name = "dashboard_admin/cities.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cities"] = City.objects.annotate(providers_count=Count("providers", distinct=True)).prefetch_related("neighborhoods")
        return ctx


class CityFormView(CrudFormView):
    module = "catalog"
    model = City
    form_class = CityForm
    audit_name = "city"
    list_url_name = "dashboard_admin:cities"
    heading_new, heading_edit = "Nouvelle ville", "Modifier la ville"


class CityDeleteView(CrudDeleteView):
    module = "catalog"
    model = City
    audit_name = "city"
    list_url_name = "dashboard_admin:cities"


class NeighborhoodFormView(CrudFormView):
    delete_url_name = "dashboard_admin:neighborhood_delete"
    module = "catalog"
    model = Neighborhood
    form_class = NeighborhoodForm
    audit_name = "neighborhood"
    list_url_name = "dashboard_admin:cities"
    heading_new, heading_edit = "Nouveau quartier", "Modifier le quartier"
    initial_from_get = ("city",)


class NeighborhoodDeleteView(CrudDeleteView):
    module = "catalog"
    model = Neighborhood
    audit_name = "neighborhood"
    list_url_name = "dashboard_admin:cities"
