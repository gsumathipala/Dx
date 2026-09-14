"""Histopathology and microbiology workflows."""
from __future__ import annotations

from django.db import models
from django.utils import timezone

from apps.common.models import ActivatableModel, IdentifiedModel


class HistoBlock(IdentifiedModel):
    class Status(models.TextChoices):
        CASSETTE_PRINTED = "Cassette Printed", "Cassette printed"
        GROSSED = "Grossed", "Grossed"
        PROCESSED = "Processed", "Processed"
        EMBEDDED = "Embedded", "Embedded"
        SECTIONED = "Sectioned", "Sectioned"
        ARCHIVED = "Archived", "Archived"

    specimen = models.ForeignKey(
        "laboratory.Specimen", on_delete=models.CASCADE, related_name="histo_blocks"
    )
    block_id = models.CharField(max_length=64, unique=True, help_text="Accession suffix, e.g. 2026-01-02-0001-A")
    tissue_type = models.CharField(max_length=128, null=True, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.CASSETTE_PRINTED)
    timestamp = models.DateTimeField(default=timezone.now)
    grossed_by = models.CharField(max_length=150, null=True, blank=True)
    archive_location = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "histo_blocks"
        ordering = ["block_id"]

    def __str__(self) -> str:
        return self.block_id


class HistoSlide(IdentifiedModel):
    class Status(models.TextChoices):
        PRINTED = "Printed", "Printed"
        STAINED = "Stained", "Stained"
        COVERSLIPPED = "Cover-slipped", "Cover-slipped"
        RELEASED = "Released", "Released to pathologist"
        ARCHIVED = "Archived", "Archived"

    block = models.ForeignKey(HistoBlock, on_delete=models.CASCADE, related_name="slides")
    slide_id = models.CharField(max_length=64, unique=True)
    stain = models.CharField(max_length=64, help_text="H&E, PAS, IHC marker, …")
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PRINTED)
    timestamp = models.DateTimeField(default=timezone.now)
    stained_by = models.CharField(max_length=150, null=True, blank=True)

    class Meta:
        db_table = "histo_slides"
        ordering = ["slide_id"]

    def __str__(self) -> str:
        return f"{self.slide_id} ({self.stain})"


class Antibiotic(IdentifiedModel, ActivatableModel):
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    drug_class = models.CharField(max_length=128, null=True, blank=True, db_column="class")
    tier = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Reporting tier for cascade/selective reporting"
    )

    class Meta:
        db_table = "antibiotics"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class MicroCulture(IdentifiedModel):
    class Status(models.TextChoices):
        SETUP = "Setup", "Set up"
        INCUBATION = "Incubation", "Incubating"
        READING = "Reading", "Being read"
        FINAL = "Final", "Final"
        NO_GROWTH = "No Growth", "No growth"

    order = models.ForeignKey("laboratory.Order", on_delete=models.CASCADE, related_name="cultures")
    specimen = models.ForeignKey(
        "laboratory.Specimen", on_delete=models.CASCADE, related_name="cultures"
    )
    test = models.ForeignKey(
        "laboratory.TestDefinition", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="cultures",
    )
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.SETUP)
    incubator_location = models.CharField(max_length=128, null=True, blank=True)
    setup_time = models.DateTimeField(null=True, blank=True)
    preliminary_result = models.JSONField(
        null=True, blank=True, help_text="Gram stain and early morphology findings"
    )
    final_result = models.JSONField(
        null=True, blank=True, help_text="Organism identification and susceptibility profile"
    )

    class Meta:
        db_table = "micro_cultures"
        ordering = ["-setup_time"]

    def __str__(self) -> str:
        return f"culture {self.id} ({self.status})"

    @property
    def incubation_hours(self) -> float | None:
        if not self.setup_time:
            return None
        return (timezone.now() - self.setup_time).total_seconds() / 3600


class SusceptibilityResult(IdentifiedModel):
    """One organism/antibiotic susceptibility pair.

    Held relationally rather than inside the culture's JSON so antibiograms and
    resistance surveillance can be queried directly.
    """

    class Interpretation(models.TextChoices):
        SUSCEPTIBLE = "S", "Susceptible"
        INTERMEDIATE = "I", "Intermediate / susceptible-dose dependent"
        RESISTANT = "R", "Resistant"
        NOT_TESTED = "NT", "Not tested"

    culture = models.ForeignKey(MicroCulture, on_delete=models.CASCADE, related_name="susceptibilities")
    organism = models.CharField(max_length=255)
    antibiotic = models.ForeignKey(Antibiotic, on_delete=models.PROTECT, related_name="susceptibilities")
    mic = models.CharField(max_length=32, null=True, blank=True, help_text="Minimum inhibitory concentration")
    zone_diameter = models.PositiveSmallIntegerField(null=True, blank=True)
    interpretation = models.CharField(max_length=4, choices=Interpretation.choices)
    reported = models.BooleanField(default=True, help_text="False when suppressed by cascade reporting")
    standard = models.CharField(max_length=32, default="CLSI", help_text="CLSI or EUCAST breakpoints")

    class Meta:
        db_table = "susceptibility_results"
        ordering = ["organism", "antibiotic__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["culture", "organism", "antibiotic"], name="susceptibility_unique"
            )
        ]

    def __str__(self) -> str:
        return f"{self.organism} / {self.antibiotic_id}: {self.interpretation}"
