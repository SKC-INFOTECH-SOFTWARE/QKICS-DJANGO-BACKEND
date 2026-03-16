from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser

from companies.models import CompanyPostSettings


class CompanyPostSettingsView(APIView):

    permission_classes = [IsAdminUser]

    def get(self, request):

        settings = CompanyPostSettings.objects.first()

        if not settings:
            settings = CompanyPostSettings.objects.create()

        data = {
            "free_posts_per_company": settings.free_posts_per_company,
            "paid_post_price": settings.paid_post_price,
        }

        return Response(data)

    def patch(self, request):

        settings = CompanyPostSettings.objects.first()

        if not settings:
            settings = CompanyPostSettings.objects.create()

        free_posts = request.data.get("free_posts_per_company")
        price = request.data.get("paid_post_price")

        if free_posts is not None:
            settings.free_posts_per_company = free_posts

        if price is not None:
            settings.paid_post_price = price

        settings.save()

        return Response({"message": "Settings updated successfully"})
