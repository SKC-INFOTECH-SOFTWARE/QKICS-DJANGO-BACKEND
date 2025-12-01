from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from .permissions import IsAdmin
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from users.models import User
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    UserUpdateSerializer,
    PasswordChangeSerializer,
    LogoutSerializer,
)
from rest_framework_simplejwt.tokens import RefreshToken


# ────────────────────── REGISTER API ──────────────────────
class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {
                    "message": "User registered successfully.",
                    "user_id": user.id,
                    "username": user.username,
                    "user_type": user.user_type,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ────────────────────── LOGIN API ──────────────────────
class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)

        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)

        response = Response(
            {
                "message": "Login successful",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "user_type": user.user_type,
                },
                "access": str(refresh.access_token),
            },
            status=status.HTTP_200_OK,
        )

        response.set_cookie(
            key="refresh_token",
            value=str(refresh),
            httponly=True,
            secure=False,
            samesite="Lax",
            max_age=30 * 24 * 60 * 60,
            path="/",
        )
        return response


# ────────────────────── GET PROFILE API ──────────────────────
class GetMyProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "phone": user.phone,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "user_type": user.user_type,
                "status": user.status,
                "profile_picture": request.build_absolute_uri(user.profile_picture.url) if user.profile_picture else None,
                "created_at": user.created_at.strftime("%Y-%m-%d %H:%M"),
                "updated_at": user.updated_at.strftime("%Y-%m-%d %H:%M"),
            },
            status=status.HTTP_200_OK,
        )


# ────────────────────── UPDATE PROFILE API ──────────────────────
class UserUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {
                    "message": "Profile updated successfully.",
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "phone": user.phone,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "user_type": user.user_type,
                        "status": user.status,
                        "profile_picture": request.build_absolute_uri(user.profile_picture.url) if user.profile_picture else None,
                    },
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ────────────────────── CHANGE PASSWORD API ──────────────────────
class PasswordChangeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Password changed successfully."},
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ────────────────────── CHECK USERNAME AVAILABILITY ──────────────────────
class UsernameCheckAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username", "").strip()

        if not username:
            return Response({"error": "Username is required."}, status=400)

        if len(username) < 3:
            return Response({"error": "Username must be at least 3 characters."}, status=400)

        exists = User.objects.filter(username__iexact=username).exists()
        return Response({"available": not exists, "username": username}, status=200)


# ────────────────────── CHECK EMAIL AVAILABILITY ──────────────────────
class EmailCheckAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email", "").strip().lower()

        if not email:
            return Response({"error": "Email is required."}, status=400)

        if "@" not in email or "." not in email.split("@")[-1]:
            return Response({"error": "Invalid email format."}, status=400)

        exists = User.objects.filter(email__iexact=email).exists()
        return Response({"available": not exists, "email": email}, status=200)


# ────────────────────── CHECK PHONE AVAILABILITY ──────────────────────
class PhoneCheckAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        phone = request.data.get("phone", "").strip()

        if not phone:
            return Response({"error": "Phone number is required."}, status=400)

        if not phone.isdigit() or len(phone) != 10:
            return Response({"error": "Phone must be 10 digits."}, status=400)

        exists = User.objects.filter(phone=phone).exists()
        return Response({"available": not exists, "phone": phone}, status=200)


# ────────────────────── LOGOUT API ──────────────────────
class LogoutAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            refresh_token = request.COOKIES.get("refresh_token")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()

            response = Response({"message": "Logged out successfully"}, status=200)
            response.delete_cookie("refresh_token")
            return response
        except Exception:
            return Response({"error": "Invalid token"}, status=400)


# ────────────────────── ADMIN USER LIST ──────────────────────
class AdminUserListAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        users = User.objects.all().order_by("-created_at")
        data = [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "phone": u.phone,
                "user_type": u.get_user_type_display(),
                "created_at": u.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for u in users
        ]
        return Response({"users": data}, status=200)


# ────────────────────── COOKIE TOKEN REFRESH ──────────────────────
class CookieTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get("refresh_token")

        if refresh_token:
            data = request.data.copy()
            data["refresh"] = refresh_token
            request._full_data = data
        elif not request.data.get("refresh"):
            return Response({"error": "Refresh token required"}, status=400)

        try:
            response = super().post(request, *args, **kwargs)
            response.data.pop("refresh", None)
            return response

        except (InvalidToken, TokenError):
            return Response({"error": "Invalid or expired refresh token"}, status=401)
