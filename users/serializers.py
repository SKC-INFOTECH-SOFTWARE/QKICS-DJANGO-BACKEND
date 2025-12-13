from rest_framework import serializers
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


# -------------------------------------
# REGISTER SERIALIZER
# -------------------------------------
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password",
            "password2",
            "phone",
            "profile_picture",
        ]

    def validate(self, data):
        if data["password"] != data["password2"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})

        validate_password(data["password"])
        return data

    def create(self, validated_data):
        validated_data.pop("password2")
        password = validated_data.pop("password")

        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


# -------------------------------------
# LOGIN SERIALIZER
# -------------------------------------
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        username = data.get("username")
        password = data.get("password")

        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError("Invalid username or password.")

        # Check business-level account status
        if user.status != "active":
            raise serializers.ValidationError(
                f"Account is {user.status}. Contact admin."
            )

        # Check Django system-level activation
        if not user.is_active:
            raise serializers.ValidationError("Account is disabled.")

        data["user"] = user
        return data


# -------------------------------------
# GENERIC USER SERIALIZER (VIEW MY PROFILE)
# -------------------------------------
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "uuid",
            "username",
            "email",
            "phone",
            "user_type",
            "status",
            "profile_picture",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "uuid",
            "user_type",
            "status",
            "created_at",
            "updated_at",
        ]


# -------------------------------------
# UPDATE USER SERIALIZER (FOR USER THEMSELVES)
# -------------------------------------
class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "phone",
            "first_name",
            "last_name",
            "profile_picture",
        ]


# -------------------------------------
# ADMIN VIEW SERIALIZER (LIST ALL USERS)
# -------------------------------------
class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "uuid",
            "username",
            "email",
            "phone",
            "user_type",
            "status",
            "profile_picture",
            "created_at",
            "updated_at",
        ]


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()
        return user


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()
