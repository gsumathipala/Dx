"""Domain vocabularies shared across the Dx applications.

These mirror the string literals used throughout the original TypeScript
implementation. Keeping them centralised avoids the casing bugs the legacy
codebase hit (for example 'completed' vs 'Completed' breaking dashboard counts).
"""
from __future__ import annotations

from django.db import models


class Role(models.TextChoices):
    ADMIN = "admin", "Administrator"
    MANAGER = "manager", "Laboratory Manager"
    SCIENTIST = "scientist", "Biomedical Scientist"
    MEDIC = "medic", "Medical Officer"
    CLERK = "clerk", "Clerk"
    PHLEBOTOMIST = "phlebotomist", "Phlebotomist"


#: Roles permitted to act on clinical laboratory data.
LAB_STAFF_ROLES = (Role.ADMIN, Role.MANAGER, Role.SCIENTIST, Role.MEDIC)
#: Roles permitted to change laboratory configuration.
MANAGEMENT_ROLES = (Role.ADMIN, Role.MANAGER)


class OrderStatus(models.TextChoices):
    PENDING = "Pending", "Pending"
    IN_PROGRESS = "In Progress", "In Progress"
    RECEIVED = "Received", "Received"
    RESULTED = "Resulted", "Resulted"
    TECHNICALLY_VALIDATED = "Technically Validated", "Technically Validated"
    CLINICALLY_VERIFIED = "Clinically Verified", "Clinically Verified"
    COMPLETED = "Completed", "Completed"
    REJECTED = "Rejected", "Rejected"
    CANCELLED = "Cancelled", "Cancelled"


class Priority(models.TextChoices):
    ROUTINE = "Routine", "Routine"
    URGENT = "Urgent", "Urgent"
    STAT = "STAT", "STAT"


class ResultFlag(models.TextChoices):
    NORMAL = "Normal", "Normal"
    LOW = "Low", "Low"
    HIGH = "High", "High"
    CRITICAL_LOW = "Critical Low", "Critical Low"
    CRITICAL_HIGH = "Critical High", "Critical High"
    ABNORMAL = "Abnormal", "Abnormal"


class Gender(models.TextChoices):
    MALE = "M", "Male"
    FEMALE = "F", "Female"
    OTHER = "O", "Other"
    UNKNOWN = "U", "Unknown"


#: Actions recorded against the immutable audit trail.
class AuditAction(models.TextChoices):
    CREATE = "CREATE", "Create"
    UPDATE = "UPDATE", "Update"
    DELETE = "DELETE", "Delete"
    LOGIN = "LOGIN", "Login"
    LOGOUT = "LOGOUT", "Logout"
    TECHNICAL_VALIDATE = "TECHNICAL_VALIDATE", "Technical validation"
    CLINICAL_VERIFY = "CLINICAL_VERIFY", "Clinical verification"
    RELEASE = "RELEASE", "Report release"
    RESTORE = "RESTORE", "Restore from backup"
