"""Read-only Django admin registration for the audit trail."""
from django.contrib import admin

from apps.audit.models import AuditEvent, ChainCheckpoint, IntegrityAlert


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    """Deliberately read-only — the trail cannot be edited from anywhere."""

    list_display = ("sequence", "timestamp", "actor_username", "action", "entity_type", "entity_id")
    list_filter = ("action", "entity_type", "source")
    search_fields = ("entity_id", "entity_label", "actor_username", "hash")
    date_hierarchy = "timestamp"
    ordering = ("-sequence",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ChainCheckpoint)
class ChainCheckpointAdmin(admin.ModelAdmin):
    list_display = ("created_at", "sequence", "event_count", "verified")
    list_filter = ("verified",)

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(IntegrityAlert)
class IntegrityAlertAdmin(admin.ModelAdmin):
    list_display = ("detected_at", "sequence", "acknowledged_by", "acknowledged_at")
    readonly_fields = ("detected_at", "sequence", "message")
