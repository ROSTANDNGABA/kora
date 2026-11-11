"""Calculs de statistiques pour le tableau de bord et la page Statistiques du prestataire."""
from datetime import timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.providers.models import ProviderDailyStat
from apps.requests_app.models import ServiceRequest

S = ServiceRequest.Status
PERIODS = (7, 30, 90)


def daily_series(profile, days):
    """Listes alignées jour par jour (jours sans activité = 0) : date, vues, clics WhatsApp, demandes reçues."""
    today = timezone.localdate()
    start = today - timedelta(days=days - 1)
    stats = {s.date: s for s in ProviderDailyStat.objects.filter(provider=profile, date__gte=start)}
    requests = dict(
        ServiceRequest.objects.filter(provider=profile, created_at__date__gte=start)
        .annotate(d=TruncDate("created_at")).values_list("d").annotate(n=Count("id")).order_by()
    )
    rows = []
    for i in range(days):
        day = start + timedelta(days=i)
        st = stats.get(day)
        rows.append({"date": day, "views": st.views if st else 0, "clicks": st.whatsapp_clicks if st else 0, "requests": requests.get(day, 0)})
    return rows


def totals(rows):
    views, clicks, requests = (sum(r[k] for r in rows) for k in ("views", "clicks", "requests"))
    return {
        "views": views, "clicks": clicks, "requests": requests,
        "contacts": clicks + requests,
        "conversion": round(100 * (clicks + requests) / views, 1) if views else 0,
    }


def request_kpis(profile):
    qs = ServiceRequest.objects.filter(provider=profile)
    total = qs.count()
    handled = qs.exclude(status=S.SENT).count()
    return {
        "received": total,
        "accepted": qs.filter(status__in=[S.ACCEPTED, S.IN_PROGRESS, S.DONE]).count(),
        "reply_rate": round(100 * handled / total) if total else None,
    }
