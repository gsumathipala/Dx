"""Patient demographics."""
from __future__ import annotations

from datetime import date

from django.db import models

from apps.common.constants import Gender
from apps.common.models import IdentifiedModel


class Patient(IdentifiedModel):
    first_name = models.CharField(max_length=128)
    last_name = models.CharField(max_length=128)
    dob = models.DateField("date of birth")
    gender = models.CharField(max_length=8, choices=Gender.choices)
    mrn = models.CharField("medical record number", max_length=64, unique=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=64, null=True, blank=True)
    address = models.TextField(null=True, blank=True)

    #: Set when an inbound ADT^A40 merges this identifier into another. The row
    #: is retained rather than deleted: reports were issued under this number
    #: and the audit trail refers to it, so it has to remain resolvable.
    merged_into = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="merged_from"
    )
    merged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "patients"
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(fields=["last_name", "first_name"]),
            models.Index(fields=["mrn"]),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.mrn})"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def age(self) -> int | None:
        """Age in completed years, or None when the date of birth is unset.

        Computed from the stored date rather than a formatted string, which is
        what caused the off-by-one-day date rendering in the legacy UI.
        """
        if not self.dob:
            return None
        today = date.today()
        return today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))

    @property
    def is_merged(self) -> bool:
        return self.merged_into_id is not None

    @property
    def age_display(self) -> str:
        years = self.age
        return f"{years}y" if years is not None else "—"
