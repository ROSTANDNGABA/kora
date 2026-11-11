from .models import Category, Subcategory


def search_suggestions():
    """Métiers proposés dans la barre de recherche (catégories puis spécialités)."""
    names = list(Category.objects.filter(is_active=True).values_list("name", flat=True))
    names += list(
        Subcategory.objects.filter(is_active=True, category__is_active=True).values_list("name", flat=True).distinct()
    )
    return names
