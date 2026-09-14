"""Users, departments, competency, audit trail and record locking."""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.common.constants import LAB_STAFF_ROLES, MANAGEMENT_ROLES, Role
from apps.common.models import ActivatableModel, IdentifiedModel, new_id


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, username: str, password: str | None = None, **extra):
        if not username:
            raise ValueError("Users must have a username")
        extra.setdefault("role", Role.SCIENTIST)
        email = extra.pop("email", None)
        user = self.model(username=username, email=self.normalize_email(email) if email else None, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username: str, password: str | None = None, **extra):
        extra.setdefault("role", Role.ADMIN)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("name", username)
        if extra.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(username, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """Laboratory user.

    Replaces the legacy ``users`` table. Passwords are stored using Django's
    hashing framework; bcrypt hashes written by the Next.js implementation are
    still verified (see ``apps.accounts.backends.LegacyCompatibleBackend``).
    """

    id = models.CharField(primary_key=True, max_length=64, default=new_id, editable=False)
    username = models.CharField(max_length=150, unique=True)
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.SCIENTIST)
    department = models.ForeignKey(
        "accounts.Department",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="members",
    )
    email = models.EmailField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["name"]

    objects = UserManager()

    class Meta:
        db_table = "users"
        ordering = ["username"]

    def __str__(self) -> str:
        return f"{self.name} ({self.username})"

    def get_full_name(self) -> str:
        return self.name or self.username

    def get_short_name(self) -> str:
        return self.username

    # ── Role helpers (mirror the RBAC checks in the original Sidebar/routes) ──

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN

    @property
    def is_manager(self) -> bool:
        return self.role in MANAGEMENT_ROLES

    @property
    def is_lab_staff(self) -> bool:
        return self.role in LAB_STAFF_ROLES

    def has_role(self, *roles: str) -> bool:
        return self.role in roles

    @property
    def department_name(self) -> str:
        return self.department.name if self.department_id else ""


class Department(IdentifiedModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=64, unique=True)
    type = models.CharField(max_length=64, default="clinical")
    description = models.TextField(null=True, blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(null=True, blank=True)
    last_modified_at = models.DateTimeField(null=True, blank=True)
    last_modified_by = models.CharField(max_length=150, null=True, blank=True)

    class Meta:
        db_table = "departments"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class RecordLock(IdentifiedModel):
    """Advisory lock preventing two users editing the same record concurrently."""

    entity_type = models.CharField(max_length=64)
    entity_id = models.CharField(max_length=64)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="locks")
    username = models.CharField(max_length=150)
    timestamp = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "record_locks"
        constraints = [
            models.UniqueConstraint(fields=["entity_type", "entity_id"], name="record_lock_unique_entity"),
        ]
        indexes = [models.Index(fields=["expires_at"])]

    def __str__(self) -> str:
        return f"{self.entity_type}/{self.entity_id} locked by {self.username}"

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= timezone.now()


class UserCompetency(IdentifiedModel):
    """CLIA-style competency assessment record."""

    class Status(models.TextChoices):
        ACTIVE = "Active", "Active"
        EXPIRED = "Expired", "Expired"
        SUSPENDED = "Suspended", "Suspended"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="competencies")
    test = models.ForeignKey(
        "laboratory.TestDefinition",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="competencies",
    )
    category = models.CharField(max_length=128, null=True, blank=True)
    competency_date = models.DateField()
    expiry_date = models.DateField()
    assessed_by = models.CharField(max_length=150)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.ACTIVE)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "user_competencies"
        ordering = ["-competency_date"]
        indexes = [models.Index(fields=["user", "status"])]

    def __str__(self) -> str:
        return f"{self.user_id} — {self.category or self.test_id}"

    @property
    def is_expired(self) -> bool:
        return self.expiry_date < timezone.localdate()

    def effective_status(self) -> str:
        """Status recomputed against today's date.

        The legacy implementation stored ``status`` as a static column, so
        lapsed competencies kept reporting 'Active' until someone edited them.
        """
        if self.status == self.Status.SUSPENDED:
            return self.Status.SUSPENDED
        return self.Status.EXPIRED if self.is_expired else self.Status.ACTIVE
