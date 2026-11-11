from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.utils.cache import patch_vary_headers
from django.views.generic import TemplateView

from apps.providers.selectors import search_providers

from .filters import MIN_RATINGS, SORT_LABELS, SearchFilters
from .models import Category, City, SearchQuery, Subcategory
from .selectors import search_suggestions

PAGE_SIZE = 12


def _is_htmx(request):
    return request.headers.get("HX-Request") == "true" and not request.headers.get("HX-Boosted")


class ListingMixin:
    """Liste filtrable : page complète, ou fragment seul quand la requête vient d'HTMX."""

    template_name = "catalog/search.html"
    fragment_template = "catalog/partials/results.html"
    fixed_category = None

    def get_template_names(self):
        return [self.fragment_template] if _is_htmx(self.request) else [self.template_name]

    def render_to_response(self, context, **kwargs):
        response = super().render_to_response(context, **kwargs)
        patch_vary_headers(response, ["HX-Request"])
        return response

    def listing_context(self):
        filters = SearchFilters.from_request(self.request.GET, fixed_category=self.fixed_category)
        page = Paginator(search_providers(**filters.kwargs), PAGE_SIZE).get_page(self.request.GET.get("page"))
        saved = False
        user = self.request.user
        if user.is_authenticated and user.is_client and filters.query_dict():
            saved = user.saved_searches.filter(query_string=filters.query_string).exists()
        return {
            "filters": filters, "page_obj": page, "results": page.object_list,
            "q": filters.q, "city": filters.city, "cities": City.objects.filter(is_active=True),
            "sort_labels": SORT_LABELS, "min_ratings": MIN_RATINGS, "search_saved": saved,
            "has_filters": bool(filters.query_dict()),
        }


class SearchView(ListingMixin, TemplateView):
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(self.listing_context())
        filters, page = ctx["filters"], ctx["page_obj"]
        self._log(filters, page)
        ctx.update(
            categories=Category.objects.filter(is_active=True),
            grouped_subcategories=[
                (c, [s for s in c.subcategories.all() if s.is_active])
                for c in Category.objects.filter(is_active=True).prefetch_related("subcategories")
            ],
            suggestions=search_suggestions(), action_url=self.request.path,
        )
        return ctx

    def _log(self, filters, page):
        """Journalise la recherche pour les statistiques, sans doubler les rafraîchissements et changements de page."""
        if not filters.q or page.number != 1 or int(self.request.GET.get("page") or 1) != 1:
            return
        signature = f"{filters.q}|{filters.city.slug if filters.city else ''}"
        session = self.request.session
        if session.get("last_search") == signature:
            return
        session["last_search"] = signature
        SearchQuery.objects.create(query=filters.q, city=filters.city, results_count=page.paginator.count)


class CategoryView(ListingMixin, TemplateView):
    template_name = "catalog/category.html"

    def get_context_data(self, slug, **kwargs):
        ctx = super().get_context_data(**kwargs)
        self.fixed_category = category = get_object_or_404(Category, slug=slug, is_active=True)
        ctx.update(self.listing_context())
        subs = list(category.subcategories.filter(is_active=True))
        ctx.update(category=category, subcategories=subs, subcategory=ctx["filters"].subcategory, action_url=self.request.path)
        return ctx
