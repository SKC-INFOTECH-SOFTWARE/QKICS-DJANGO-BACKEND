from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.hashers import make_password, check_password
from django.core.validators import RegexValidator
from django.utils import timezone
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
import uuid
import secrets
from datetime import timedelta
from django.conf import settings
from django.core.files.storage import default_storage


class User(AbstractUser):

    USER_TYPES = [
        ("superadmin", "Super Admin"),
        ("admin", "Admin"),
        ("expert", "Expert"),
        ("entrepreneur", "Entrepreneur"),
        ("investor", "Investor"),
        ("normal", "Normal User"),
    ]

    STATUS_TYPES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("banned", "Banned"),
    ]

    uuid = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )
    # USER ROLE
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default="normal")

    # ACCOUNT STATUS
    status = models.CharField(max_length=20, choices=STATUS_TYPES, default="active")

    # OPTIONAL PHONE NUMBER
    phone = models.CharField(
        max_length=15,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^[0-9]{7,15}$",
                message="Phone number must contain only digits (7–15 digits).",
            )
        ],
    )

    # OPTIONAL BASIC PROFILE PICTURE
    profile_picture = models.ImageField(
        upload_to="users/profile_pics/", blank=True, null=True
    )

    # TIMESTAMPS
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return f"{self.username} ({self.user_type})"

    def save(self, *args, **kwargs):
        # Get the previous record (if exists)
        try:
            old = User.objects.get(pk=self.pk)
            old_image = old.profile_picture
        except User.DoesNotExist:
            old = None
            old_image = None

        # CASE 1 — User REMOVED the picture
        if not self.profile_picture:
            if old_image and default_storage.exists(old_image.path):
                default_storage.delete(old_image.path)
            return super().save(*args, **kwargs)

        # CASE 2 — User did NOT upload a new picture → DO NOTHING
        if old_image and self.profile_picture == old_image:
            return super().save(*args, **kwargs)

        # CASE 3 — New image uploaded, delete old one
        if old_image and default_storage.exists(old_image.path):
            default_storage.delete(old_image.path)

        # COMPRESS NEW IMAGE
        img = Image.open(self.profile_picture)

        if img.mode != "RGB":
            img = img.convert("RGB")

        buffer = BytesIO()
        quality = 85

        while True:
            buffer.seek(0)
            buffer.truncate()
            img.save(buffer, format="JPEG", quality=quality)
            size_kb = buffer.tell() / 1024
            if size_kb <= 200 or quality <= 40:
                break
            quality -= 5

        filename = f"user_{self.uuid}.jpg"

        self.profile_picture = ContentFile(buffer.getvalue(), name=filename)

        super().save(*args, **kwargs)


class EmailOTP(models.Model):
    """
    One-time codes emailed for two purposes:
      - `register`: verify an email BEFORE the account is created.
      - `reset`:    verify ownership before resetting a forgotten password.

    The plaintext code is NEVER stored — only a password-hashed digest. A row
    is consumed (`is_used=True`) once it fulfils its purpose (account created /
    password reset). For registration the code is first marked verified
    (`verified_at`), which lets `RegisterAPIView` trust the email within
    OTP_VERIFIED_WINDOW_MINUTES, then consumed when the account is created.
    """

    PURPOSE_REGISTER = "register"
    PURPOSE_RESET = "reset"
    PURPOSE_CHOICES = [
        (PURPOSE_REGISTER, "Email Verification"),
        (PURPOSE_RESET, "Password Reset"),
    ]

    email = models.EmailField(db_index=True)
    code_hash = models.CharField(max_length=128)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    attempts = models.PositiveSmallIntegerField(default=0)
    verified_at = models.DateTimeField(null=True, blank=True)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        indexes = [
            models.Index(fields=["email", "purpose", "is_used"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"OTP({self.purpose}) for {self.email}"

    # ---- lifecycle helpers -------------------------------------------------
    @staticmethod
    def generate_code():
        """Return a fresh zero-padded numeric OTP of settings.OTP_LENGTH digits."""
        length = getattr(settings, "OTP_LENGTH", 6)
        upper = 10 ** length
        return str(secrets.randbelow(upper)).zfill(length)

    @classmethod
    def issue(cls, *, email, purpose):
        """
        Create + persist a new OTP for (email, purpose) and return
        (instance, plaintext_code). The caller emails the plaintext code; the
        DB keeps only the hash.
        """
        code = cls.generate_code()
        exp_minutes = getattr(settings, "OTP_EXP_MINUTES", 10)
        otp = cls.objects.create(
            email=email.strip().lower(),
            code_hash=make_password(code),
            purpose=purpose,
            expires_at=timezone.now() + timedelta(minutes=exp_minutes),
        )
        return otp, code

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    def check_code(self, code):
        return check_password((code or "").strip(), self.code_hash)
