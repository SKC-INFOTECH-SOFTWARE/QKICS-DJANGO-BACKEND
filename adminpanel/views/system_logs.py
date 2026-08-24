"""
System logs (superadmin).

Powers the admin "Logs" tab. Lists application log records captured into the
SystemLog table by adminpanel.logging_handler.DatabaseLogHandler (root logger,
WARNING+). Superadmin only — matches the sidebar gating.
"""
from rest_framework import generics, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

from users.permissions import IsSuperAdmin
from adminpanel.models import SystemLog
from adminpanel.serializers import AdminSystemLogSerializer
from adminpanel.pagination import AdminPagination


class AdminSystemLogListView(generics.ListAPIView):
    serializer_class = AdminSystemLogSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    pagination_class = AdminPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["level", "category"]
    search_fields = ["message", "logger_name", "detail"]

    def get_queryset(self):
        return SystemLog.objects.all().order_by("-created_at")


class AdminSystemLogStatsView(APIView):
    """Small summary for the logs page header (counts by level)."""
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        from django.db.models import Count

        by_level = {
            row["level"]: row["n"]
            for row in SystemLog.objects.values("level").annotate(n=Count("id"))
        }
        return Response({
            "total":    SystemLog.objects.count(),
            "errors":   by_level.get(SystemLog.LEVEL_ERROR, 0) + by_level.get(SystemLog.LEVEL_CRITICAL, 0),
            "warnings": by_level.get(SystemLog.LEVEL_WARNING, 0),
            "by_level": by_level,
        })
