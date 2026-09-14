"""Abstract base models shared across every Dx application.

The original Drizzle schema used opaque text primary keys (mostly UUID v4, but
a few seeded rows use readable ids such as ``admin``). ``IdentifiedModel``
preserves that so historic data migrates without rewriting foreign keys.
"""
from __future__ import annotations

import uuid

from django.db import models


def new_id() -> str:
    """Generate a UUID4 primary key, matching the legacy id format."""
    return str(uuid.uuid4())


class IdentifiedModel(models.Model):
    """Base model with the legacy string primary key."""

    id = models.CharField(primary_key=True, max_length=64, default=new_id, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    """Adds creation/modification bookkeeping."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ActiveQuerySet(models.QuerySet):
    def active(self):
        return self.filter(active=True)


class ActivatableModel(models.Model):
    """Base for reference/config tables that are soft-disabled rather than deleted."""

    active = models.BooleanField(default=True)

    objects = ActiveQuerySet.as_manager()

    class Meta:
        abstract = True
