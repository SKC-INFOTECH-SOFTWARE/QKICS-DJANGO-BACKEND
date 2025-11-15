from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from users.models import User
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    UserUpdateSerializer,
    PasswordChangeSerializer,
    LogoutSerializer,
)
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated


# Register API
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


# Login API
class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data["user"]
            refresh = RefreshToken.for_user(user)
            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "user_type": user.user_type,
                        "status": user.status,
                    },
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)


# Update User API patch
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
                    },
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Change Password API
class PasswordChangeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Password changed successfully."}, status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Username Check API
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


# Email Check API
class EmailCheckAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email", "").strip().lower()

        if not email:
            return Response(
                {"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Basic email format check
        if "@" not in email or "." not in email.split("@")[-1]:
            return Response(
                {"error": "Invalid email format."}, status=status.HTTP_400_BAD_REQUEST
            )

        exists = User.objects.filter(email__iexact=email).exists()
        return Response(
            {"available": not exists, "email": email}, status=status.HTTP_200_OK
        )


# Phone Check API
class PhoneCheckAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        phone = request.data.get("phone", "").strip()

        if not phone:
            return Response(
                {"error": "Phone number is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Basic validation: 10 digits only (India)
        if not phone.isdigit() or len(phone) != 10:
            return Response(
                {"error": "Phone must be 10 digits (India only)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        exists = User.objects.filter(phone=phone).exists()
        return Response(
            {"available": not exists, "phone": phone}, status=status.HTTP_200_OK
        )


class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        if serializer.is_valid():
            try:
                token = serializer.validated_data["refresh"]
                from rest_framework_simplejwt.tokens import RefreshToken

                refresh_token = RefreshToken(token)
                refresh_token.blacklist()
                return Response(
                    {"message": "Successfully logged out."}, status=status.HTTP_200_OK
                )
            except Exception as e:
                return Response(
                    {"error": "Token is already blacklisted or invalid."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
