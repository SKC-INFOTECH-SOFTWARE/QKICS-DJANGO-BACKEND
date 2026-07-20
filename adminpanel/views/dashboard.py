from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum, DecimalField
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsAdmin

User = get_user_model()


class AdminDashboardStatsView(APIView):
    """
    GET /api/v1/admin/dashboard/stats/
    Admin dashboard: real aggregated platform metrics.
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        now = timezone.now()

        # ── User counts (single query, conditional aggregation) ──
        user_agg = User.objects.aggregate(
            total=Count("id"),
            normal=Count("id", filter=Q(user_type="normal")),
            expert=Count("id", filter=Q(user_type="expert")),
            entrepreneur=Count("id", filter=Q(user_type="entrepreneur")),
            investor=Count("id", filter=Q(user_type="investor")),
            admin=Count("id", filter=Q(user_type__in=["admin", "superadmin"])),
            active=Count("id", filter=Q(is_active=True)),
        )

        # ── Content / engagement counts (lazy imports keep this app decoupled) ──
        content = {"posts": 0, "companies": 0, "ads_active": 0}
        engagement = {"bookings": 0, "active_subscriptions": 0}
        try:
            from community.models import Post
            content["posts"] = Post.objects.count()
        except Exception:
            pass
        try:
            from companies.models import Company
            content["companies"] = Company.objects.count()
        except Exception:
            pass
        try:
            from ads.models import Advertisement
            content["ads_active"] = Advertisement.objects.filter(is_active=True).count()
        except Exception:
            pass
        try:
            from bookings.models import Booking, InvestorBooking
            engagement["bookings"] = Booking.objects.count() + InvestorBooking.objects.count()
        except Exception:
            pass
        try:
            from subscriptions.models import UserSubscription
            engagement["active_subscriptions"] = UserSubscription.objects.filter(
                is_active=True, end_date__gt=now
            ).count()
        except Exception:
            pass

        # ── Revenue (successful payments only) ──
        revenue = {"total": 0, "this_month": 0, "currency": "INR"}
        revenue_series = []
        try:
            from payments.models import Payment

            success = Payment.objects.filter(status=Payment.STATUS_SUCCESS)
            revenue["total"] = float(
                success.aggregate(
                    s=Sum("amount", output_field=DecimalField())
                )["s"] or 0
            )
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            revenue["this_month"] = float(
                success.filter(created_at__gte=month_start).aggregate(
                    s=Sum("amount", output_field=DecimalField())
                )["s"] or 0
            )
            revenue_series = self._monthly_series(
                success, "created_at", now, value="amount"
            )
        except Exception:
            pass

        # ── New users over the last 6 months ──
        user_growth = self._monthly_series(User.objects.all(), "date_joined", now)

        # ── Recent signups ──
        recent = User.objects.order_by("-date_joined")[:6]
        recent_users = [
            {
                "id": u.id,
                "username": u.username,
                "full_name": (f"{u.first_name} {u.last_name}".strip() or u.username),
                "email": u.email,
                "user_type": u.user_type,
                "date_joined": u.date_joined,
                "profile_picture": (
                    request.build_absolute_uri(u.profile_picture.url)
                    if getattr(u, "profile_picture", None) else None
                ),
            }
            for u in recent
        ]

        return Response({
            "users": user_agg,
            "content": content,
            "engagement": engagement,
            "revenue": revenue,
            "user_growth": user_growth,
            "revenue_series": revenue_series,
            "recent_users": recent_users,
        })

    @staticmethod
    def _monthly_series(qs, date_field, now, value=None, months=6):
        """Return [{month: 'Feb 25', count/amount: N}] for the last `months` months."""
        # Build the ordered list of the last `months` month-buckets.
        buckets = []
        y, m = now.year, now.month
        for _ in range(months):
            buckets.append((y, m))
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        buckets.reverse()

        start_year, start_month = buckets[0]
        from datetime import datetime
        naive_start = datetime(start_year, start_month, 1)
        start = timezone.make_aware(naive_start) if timezone.is_naive(naive_start) else naive_start

        agg = (
            qs.filter(**{f"{date_field}__gte": start})
            .annotate(bucket=TruncMonth(date_field))
            .values("bucket")
            .annotate(
                value=Sum(value, output_field=DecimalField()) if value else Count("id")
            )
        )
        lookup = {
            (row["bucket"].year, row["bucket"].month): float(row["value"] or 0)
            for row in agg if row["bucket"]
        }

        labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        key = "amount" if value else "count"
        return [
            {"month": f"{labels[mm - 1]} {str(yy)[2:]}", key: lookup.get((yy, mm), 0)}
            for (yy, mm) in buckets
        ]
