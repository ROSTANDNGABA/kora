from apps.providers.models import ProviderProfile, Verification
from apps.reviews.models import Report


def admin_badges():
    P = ProviderProfile.Status
    return {
        "pending_providers": ProviderProfile.objects.filter(status=P.PENDING).count()
        + ProviderProfile.objects.filter(pending_category__isnull=False).exclude(status=P.PENDING).count(),
        "pending_verifications": Verification.objects.filter(status=Verification.Status.PENDING).count(),
        "pending_reports": Report.objects.filter(status=Report.Status.PENDING).count(),
    }
