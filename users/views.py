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
        """
        Register a new user.
        Required: username, user_type (normal/entrepreneur/expert/investor), password
        Returns: user_id, username, user_type, is_verified (False)
        """
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {
                    "message": "User registered successfully.",
                    "user_id": user.id,
                    "username": user.username,
                    "user_type": user.user_type,
                    "is_verified": user.is_verified,
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
                    "is_verified": user.is_verified,
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
            max_age=30 * 24 * 60 * 60,  # 30 days
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
                "is_verified": user.is_verified,
                "created_at": user.created_at.strftime("%Y-%m-%d %H:%M"),
                "updated_at": user.updated_at.strftime("%Y-%m-%d %H:%M"),
            },
            status=status.HTTP_200_OK,
        )


# ────────────────────── UPDATE PROFILE API ──────────────────────
class UserUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        """
        Update logged-in user's profile (email, phone, name)
        """
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
                        "is_verified": user.is_verified,
                    },
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ────────────────────── CHANGE PASSWORD API ──────────────────────
class PasswordChangeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Change password for logged-in user.
        Requires old password.
        """
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
            return Response(
                {"error": "Username is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        if len(username) < 3:
            return Response(
                {"error": "Username must be at least 3 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        exists = User.objects.filter(username__iexact=username).exists()
        return Response(
            {"available": not exists, "username": username}, status=status.HTTP_200_OK
        )


# ────────────────────── CHECK EMAIL AVAILABILITY ──────────────────────
class EmailCheckAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email", "").strip().lower()

        if not email:
            return Response(
                {"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        if "@" not in email or "." not in email.split("@")[-1]:
            return Response(
                {"error": "Invalid email format."}, status=status.HTTP_400_BAD_REQUEST
            )

        exists = User.objects.filter(email__iexact=email).exists()
        return Response(
            {"available": not exists, "email": email}, status=status.HTTP_200_OK
        )


# ────────────────────── CHECK PHONE AVAILABILITY ──────────────────────
class PhoneCheckAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        phone = request.data.get("phone", "").strip()

        if not phone:
            return Response(
                {"error": "Phone number is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not phone.isdigit() or len(phone) != 10:
            return Response(
                {"error": "Phone must be 10 digits (India only)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        exists = User.objects.filter(phone=phone).exists()
        return Response(
            {"available": not exists, "phone": phone}, status=status.HTTP_200_OK
        )


# ────────────────────── LOGOUT API (BLACKLIST REFRESH TOKEN) ──────────────────────
class LogoutAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            refresh_token = request.COOKIES.get("refresh_token")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()

            response = Response(
                {"message": "Logged out successfully"}, status=status.HTTP_200_OK
            )
            response.delete_cookie("refresh_token")
            return response
        except Exception:
            return Response(
                {"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST
            )


# ────────────────────── Admin User List API ──────────────────────
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
                "is_verified": u.is_verified,
                "created_at": u.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for u in users
        ]
        return Response({"users": data}, status=status.HTTP_200_OK)


# ────────────────────── Admin Verify User API ──────────────────────
class AdminVerifyUserAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def patch(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found."}, status=status.HTTP_404_NOT_FOUND
            )

        action = request.data.get("action")
        if action not in ["approve", "reject"]:
            return Response(
                {"error": "action must be 'approve' or 'reject'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.is_verified = action == "approve"
        user.save()

        return Response(
            {
                "message": f"User {user.username} has been {action}d.",
                "user_id": user.id,
                "is_verified": user.is_verified,
            },
            status=status.HTTP_200_OK,
        )


class CookieTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        # 1. Read refresh token from HttpOnly cookie
        refresh_token = request.COOKIES.get("refresh_token")

        if refresh_token:
            # Inject into request.data (immutable → must use _full_data)
            mutable_data = request.data.copy()
            mutable_data["refresh"] = refresh_token
            request._full_data = mutable_data

        # 2. Fallback for testing (optional — safe to keep)
        elif not request.data.get("refresh"):
            return Response({"error": "Refresh token required"}, status=400)

        try:
            response = super().post(request, *args, **kwargs)

            # ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ←
            # FINAL FIX: REMOVE refresh token from response
            if "refresh" in response.data:
                del response.data["refresh"]   # ← NEVER SEND NEW REFRESH TOKEN
            # ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ←

            return response

        except (InvalidToken, TokenError):
            return Response(
                {"error": "Invalid or expired refresh token"},
                status=status.HTTP_401_UNAUTHORIZED
            )