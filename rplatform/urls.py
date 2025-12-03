from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path('api/v1/auth/', include('users.urls')),
    path("api/v1/experts/", include("experts.urls")),
    path("api/v1/entrepreneurs/", include("entrepreneurs.urls")),
    path("api/v1/community/", include("community.urls")),
    path("api/v1/investors/", include("investors.urls")),
    path("api/v1/chat/", include("chat.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)