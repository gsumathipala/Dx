"""Role-aware navigation, ported from the React Sidebar component."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NavItem:
    label: str
    url_name: str
    icon: str
    visible: bool = True


def _sections(user):
    """Build the sidebar for this user's role.

    Mirrors the RBAC of the original Sidebar: lab staff see clinical screens,
    managers see configuration, admins see everything.
    """
    is_admin = user.is_admin
    is_manager = user.is_manager
    is_lab = user.is_lab_staff
    is_clerk = user.role == "clerk"
    department = user.department_name

    return [
        ("Workspace", [
            NavItem("Dashboard", "operations:dashboard", "layout-dashboard"),
            NavItem("Messages", "operations:messages", "mail"),
            NavItem("Critical Values", "clinical:critical_values", "bell", is_lab),
            NavItem("Reports", "reporting:reports", "file-text"),
            NavItem("Cumulative Report", "reporting:cumulative", "trending-up", is_lab),
            NavItem("Email Delivery", "reporting:email_delivery", "send", is_manager),
        ]),
        ("Samples & Tracking", [
            NavItem("Accessioning", "laboratory:accessioning", "test-tube", is_lab or is_clerk),
            NavItem("Specimen Receiving", "laboratory:receiving", "flask-conical", is_lab or is_clerk),
            NavItem("Phlebotomy", "laboratory:phlebotomy", "syringe", is_lab or is_clerk),
            NavItem("Tracking (CoC)", "operations:tracking", "map-pin"),
            NavItem("Storage", "operations:storage", "archive", is_lab),
            NavItem("Inventory", "inventory:list", "box", is_lab),
        ]),
        ("Clinical Analysis", [
            NavItem("Results Entry", "laboratory:results", "microscope", is_lab),
            NavItem("Workflow Queues", "operations:queues", "layers", is_lab),
            NavItem("Worksheets", "operations:worksheets", "clipboard-list", is_lab),
            NavItem("QC & Calibration", "quality:qc", "activity", is_lab),
            NavItem("Epidemiology", "clinical:epidemiology", "globe", is_manager),
            NavItem("Histopathology", "specialty:histology", "microscope",
                    is_admin or department == "Histopathology"),
            NavItem("Microbiology", "specialty:microbiology", "microscope",
                    is_admin or department == "Microbiology"),
        ]),
        ("Quality & Compliance", [
            NavItem("Audit Trail", "audit:trail", "shield-check"),
            NavItem("Chain Integrity", "audit:integrity", "fingerprint", is_manager),
            NavItem("CAPA / Nonconformance", "compliance:capa_list", "alert-triangle", is_lab),
            NavItem("Proficiency Testing", "compliance:pt_list", "award", is_lab),
            NavItem("Method Validation", "compliance:validation_list", "check-circle", is_manager),
            NavItem("Risk Register", "compliance:risk_list", "alert-octagon", is_manager),
            NavItem("Change Control", "compliance:change_list", "git-branch", is_manager),
            NavItem("Compliance Dashboard", "compliance:dashboard", "clipboard-check", is_manager),
        ]),
        ("Management", [
            NavItem("Billing", "billing:list", "banknote", is_lab),
            NavItem("Equipment", "quality:equipment", "thermometer"),
            NavItem("Documents", "reporting:documents", "file"),
            NavItem("Training", "compliance:training_list", "graduation-cap"),
            NavItem("Feedback", "operations:feedback", "message-square"),
        ]),
    ]


def _admin_items(user):
    is_admin = user.is_admin
    is_manager = user.is_manager
    return [
        NavItem("User Management", "accounts:user_list", "users", is_admin),
        NavItem("Patient Data", "patients:admin_list", "users", is_manager),
        NavItem("Test Definitions", "laboratory:test_list", "test-tube", is_manager),
        NavItem("Delta Check Rules", "clinical:delta_rules", "git-branch", is_manager),
        NavItem("Reflex Testing Rules", "clinical:reflex_rules", "repeat", is_manager),
        NavItem("Demographic Ref Ranges", "clinical:demographic_ranges", "users", is_manager),
        NavItem("Calculated Tests", "clinical:calculated_tests", "calculator", is_manager),
        NavItem("TAT Thresholds", "operations:tat_thresholds", "calendar", is_manager),
        NavItem("User Competency", "accounts:competency_list", "user-check", is_manager),
        NavItem("Distribution Rules", "reporting:distribution_rules", "send", is_manager),
        NavItem("Requester Registry", "reporting:requester_list", "building", is_manager),
        NavItem("Sample Retention", "laboratory:retention_list", "trash-2", is_manager),
        NavItem("Retention Schedule", "compliance:retention_schedule", "calendar-clock", is_manager),
        NavItem("LOINC Catalogue", "interop:loinc_list", "book-open", is_manager),
        NavItem("Instrument Interfaces", "interop:interface_list", "plug", is_manager),
        NavItem("KPI Dashboard", "operations:kpi", "bar-chart", is_manager),
        NavItem("Rejection Criteria", "quality:criteria_list", "ban", is_manager),
        NavItem("Auth Queues", "laboratory:queue_list", "shield-check", is_manager),
        NavItem("Departments", "accounts:department_list", "layers", is_admin),
        NavItem("Notifiable Conditions", "clinical:notifiable_list", "alert-circle", is_admin),
        NavItem("Alert Log", "operations:alert_list", "alert-circle", is_manager),
        NavItem("PHI Access Log", "compliance:phi_access_log", "eye", is_admin),
        NavItem("Disclosure Accounting", "compliance:disclosure_list", "share-2", is_admin),
        NavItem("Backup & Maintenance", "operations:backup", "database", is_admin),
        NavItem("Configuration", "operations:settings", "settings", is_manager),
    ]


def navigation(request):
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        return {}

    sections = [
        (title, [item for item in items if item.visible])
        for title, items in _sections(user)
    ]
    return {
        "nav_sections": [(title, items) for title, items in sections if items],
        "nav_admin_items": [item for item in _admin_items(user) if item.visible],
    }
