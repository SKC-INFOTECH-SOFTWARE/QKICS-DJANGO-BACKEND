from rest_framework import serializers
from .models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate


# ────────────────────── REGISTER SERIALIZER ──────────────────────
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        help_text="Password (min 8 chars, not too common)",
    )
    password2 = serializers.CharField(write_only=True, help_text="Confirm password")
    user_type = serializers.ChoiceField(
        choices=[
            ("normal", "Normal User"),
            ("entrepreneur", "Entrepreneur"),
            ("expert", "Expert"),
            ("investor", "Investor"),
        ],
        required=True,
        help_text="Choose your role on the platform",
    )

    class Meta:
        model = User
        fields = ["username", "email", "phone", "user_type", "password", "password2"]

    def validate(self, data):
        """Ensure passwords match"""
        if data["password"] != data["password2"]:
            raise serializers.ValidationError({"password": "Passwords must match."})
        return data

    def create(self, validated_data):
        """Create user with selected role and pending verification"""
        validated_data.pop("password2")
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            phone=validated_data.get("phone", ""),
            user_type=validated_data["user_type",],
            password=validated_data["password"],
        )
        user.status = "active"
        user.is_verified = False
        user.save()
        return user


# ────────────────────── LOGIN SERIALIZER ──────────────────────
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(help_text="Username or email")
    password = serializers.CharField(write_only=True, help_text="Password")

    def validate(self, data):
        """Authenticate + check account status"""
        user = authenticate(username=data["username"], password=data["password"])
        if not user:
            raise serializers.ValidationError("Invalid credentials.")

        if user.status != "active":
            raise serializers.ValidationError(
                f"Account is {user.status}. Contact admin."
            )

        if not user.is_active:
            raise serializers.ValidationError("Account is disabled.")

        data["user"] = user
        return data


# ────────────────────── PROFILE UPDATE SERIALIZER ──────────────────────
class UserUpdateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=False)
    phone = serializers.CharField(max_length=15, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ["email", "phone", "first_name", "last_name"]

    def update(self, instance, validated_data):
        """Update only allowed fields"""
        instance.email = validated_data.get("email", instance.email)
        instance.phone = validated_data.get("phone", instance.phone)
        instance.first_name = validated_data.get("first_name", instance.first_name)
        instance.last_name = validated_data.get("last_name", instance.last_name)
        instance.save()
        return instance


# ────────────────────── PASSWORD CHANGE SERIALIZER ──────────────────────
class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(
        write_only=True, validators=[validate_password]
    )
    new_password2 = serializers.CharField(write_only=True)

    def validate(self, data):
        if data["new_password"] != data["new_password2"]:
            raise serializers.ValidationError({"new_password": "Passwords must match."})
        return data

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def save(self):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()
        return user


# ────────────────────── LOGOUT SERIALIZER ──────────────────────
class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True)

    def validate_refresh(self, value):
        from rest_framework_simplejwt.tokens import RefreshToken

        try:
            RefreshToken(value)
        except Exception:
            raise serializers.ValidationError("Invalid or expired refresh token.")
        return value
