"""Role-aware navigation.

The sidebar carries only what someone uses during a shift. Configuration — 25
screens that are visited occasionally and never hunted for by scanning a list —
lives behind a single Settings link that opens a searchable index. An admin's
sidebar went from 57 links to 10 as a result.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NavItem:
    label: str
    url_name: str
    icon: str
    visible: bool = True


@dataclass(frozen=True)
class SettingsItem:
    """A configuration screen, listed on the settings index rather than the sidebar."""

    label: str
    url_name: str
    group: str
    description: str
    visible: bool = True
    #: Extra words people might search for that are not in the label.
    keywords: str = ""
    #: True for system administration, False for laboratory configuration.
    #: The installer sees only the former: the test catalogue, clinical rules
    #: and QC targets are the laboratory's decisions, not the maintainer's.
    system: bool = False

    @property
    def haystack(self) -> str:
        return f"{self.label} {self.group} {self.description} {self.keywords}".lower()


def _installer_workspace(user):
    """The installer commissions and maintains; it runs no laboratory work."""
    return [
        NavItem("Maintenance", "operations:backup", "wrench"),
        NavItem("Users", "accounts:user_list", "users"),
        NavItem("Departments", "accounts:department_list", "layers"),
        NavItem("Instrument interfaces", "interop:interface_list", "plug"),
        NavItem("Configuration", "operations:setting_list", "settings"),
        NavItem("Settings index", "operations:settings_index", "list"),
        NavItem("My password", "compliance:password_change", "key"),
    ]


def _installer_oversight(user):
    return [
        NavItem("Audit Trail", "audit:trail", "shield-check"),
        NavItem("Chain Integrity", "audit:integrity", "fingerprint"),
        NavItem("Change Control", "compliance:change_list", "git-branch"),
        NavItem("System Alerts", "operations:alert_list", "alert-circle"),
    ]


def _workspace(user):
    """What a user needs during a shift, in the order they need it."""
    is_lab = user.is_lab_staff
    is_clerk = user.role == "clerk"
    is_collector = user.role in {"clerk", "phlebotomist"}
    department = user.department_name

    return [
        NavItem("Dashboard", "operations:dashboard", "layout-dashboard"),
        NavItem("Search", "operations:search", "search"),
        NavItem("Worklist", "laboratory:results", "microscope", is_lab),
        NavItem("Accessioning", "laboratory:accessioning", "test-tube", is_lab or is_clerk),
        NavItem("Receiving", "laboratory:receiving", "flask-conical", is_lab or is_clerk),
        NavItem("Phlebotomy", "laboratory:phlebotomy_list", "syringe", is_collector or is_lab),
        NavItem("Critical Values", "clinical:critical_values", "bell", is_lab),
        NavItem("Quality Control", "quality:qc", "activity", is_lab),
        NavItem("Reports", "reporting:reports", "file-text"),
        NavItem("Messages", "operations:messages", "mail"),
        NavItem("Histopathology", "specialty:histology", "microscope",
                user.is_admin or department == "Histopathology"),
        NavItem("Microbiology", "specialty:microbiology", "microscope",
                user.is_admin or department == "Microbiology"),
    ]


def _oversight(user):
    """Screens a manager checks daily, kept out of the working set."""
    return [
        NavItem("Compliance", "compliance:dashboard", "clipboard-check", user.is_manager),
        NavItem("Audit Trail", "audit:trail", "shield-check"),
        NavItem("Nonconformances", "compliance:capa_list", "alert-triangle", user.is_lab_staff),
        NavItem("Turnaround", "operations:tat", "clock", user.is_lab_staff),
        NavItem("Settings", "operations:settings_index", "settings", user.is_manager),
        NavItem("My password", "compliance:password_change", "key"),
    ]


def settings_index(user):
    """Every configuration screen, grouped and searchable.

    Nobody scans a 25-item list for "Delta Check Rules" — they type "delta".

    An installer is shown only the system entries: laboratory configuration
    belongs to the laboratory, and several of those screens would reveal
    patient-linked content anyway.
    """
    is_admin = user.is_admin
    is_manager = user.is_manager
    is_lab = user.is_lab_staff
    is_installer = user.is_installer
    if is_installer:
        # An installer holds system authority regardless of these role flags.
        is_admin = is_manager = True
        is_lab = False

    items = [
        # ── Test catalogue ───────────────────────────────────────────────────
        SettingsItem("Test definitions", "laboratory:test_list", "Test catalogue",
                     "Analytes, units, reference intervals and critical limits.",
                     is_manager, "assay panel loinc range"),
        SettingsItem("Calculated tests", "clinical:calculated_list", "Test catalogue",
                     "Derived analytes such as eGFR, LDL and anion gap.", is_manager,
                     "egfr ldl formula derived"),
        SettingsItem("Demographic reference intervals", "clinical:range_list", "Test catalogue",
                     "Age, sex and pregnancy specific intervals.", is_manager,
                     "paediatric adult range normal"),
        SettingsItem("LOINC catalogue", "interop:loinc_list", "Test catalogue",
                     "Standard codes for external exchange.", is_manager, "coding standard"),

        # ── Clinical rules ───────────────────────────────────────────────────
        SettingsItem("Delta check rules", "clinical:delta_rule_list", "Clinical rules",
                     "Flag results that change sharply from the patient's last.",
                     is_manager, "change trend previous"),
        SettingsItem("Reflex testing rules", "clinical:reflex_rule_list", "Clinical rules",
                     "Add a follow-on test automatically when a result triggers it.",
                     is_manager, "cascade add-on automatic"),
        SettingsItem("Notifiable conditions", "clinical:notifiable_list", "Clinical rules",
                     "Conditions reported to public health, and their deadlines.",
                     is_admin, "epidemiology public health surveillance"),
        SettingsItem("Delta check flags", "clinical:delta_flag_list", "Clinical rules",
                     "Results the delta rules have flagged.", is_lab, "flagged"),

        # ── Quality ──────────────────────────────────────────────────────────
        SettingsItem("QC materials", "quality:material_list", "Quality",
                     "Control lots and their expiry.", is_lab, "control lot"),
        SettingsItem("QC target values", "quality:definition_list", "Quality",
                     "Mean and SD per analyte per control lot.", is_manager,
                     "mean sd westgard"),
        SettingsItem("Equipment", "quality:equipment_list", "Quality",
                     "Instruments, service and calibration dates.", is_manager,
                     "instrument analyser calibration maintenance"),
        SettingsItem("Equipment log", "quality:equipment_log_list", "Quality",
                     "Maintenance, calibration and repair history.", is_lab, "service repair"),
        SettingsItem("Rejection criteria", "quality:criterion_list", "Quality",
                     "Reasons a specimen may be rejected at reception.", is_manager,
                     "haemolysed clotted unlabelled"),

        # ── Compliance ───────────────────────────────────────────────────────
        SettingsItem("Proficiency testing", "compliance:pt_list", "Compliance",
                     "External quality assessment surveys and their deadlines.",
                     is_lab, "eqa survey cap neqas"),
        SettingsItem("Proficiency results", "compliance:pt_result_list", "Compliance",
                     "Graded analyte results from EQA surveys.", is_lab, "eqa grade"),
        SettingsItem("Method validation", "compliance:validation_list", "Compliance",
                     "Accuracy, precision, reportable range and reference interval.",
                     is_manager, "verification clia 493.1253"),
        SettingsItem("Risk register", "compliance:risk_list", "Compliance",
                     "Assessed risks and their mitigations.", is_manager, "iso 15189 hazard"),
        SettingsItem("Change control", "compliance:change_list", "Compliance",
                     "Changes affecting result production, and their validation.",
                     is_manager, "part 11 software", system=True),
        SettingsItem("Training records", "compliance:training_list", "Compliance",
                     "Training delivered and assessed.", True, "competency staff"),
        SettingsItem("User competency", "accounts:competency_list", "Compliance",
                     "Who may report which tests, and until when.", is_manager,
                     "clia 493.1451 assessment"),
        SettingsItem("Record retention", "compliance:retention_list", "Compliance",
                     "How long each class of record is kept.", is_manager,
                     "clia 493.1105 destruction"),
        SettingsItem("Sample retention", "laboratory:retention_list", "Compliance",
                     "How long each specimen type is kept before disposal.", is_manager,
                     "specimen storage disposal"),

        # ── Access and privacy ───────────────────────────────────────────────
        SettingsItem("Users", "accounts:user_list", "Access and privacy",
                     "Named accounts, roles, password resets and account suspension.",
                     is_admin, "staff login account password reset disable", system=True),
        SettingsItem("Departments", "accounts:department_list", "Access and privacy",
                     "Disciplines the laboratory is organised into.", is_admin, "discipline", system=True),
        SettingsItem("Authorisation queues", "laboratory:queue_list", "Access and privacy",
                     "How work awaiting authorisation is segregated.", is_manager, "workflow"),
        SettingsItem("PHI access log", "compliance:phi_access_list", "Access and privacy",
                     "Who viewed identifiable patient information.", is_admin,
                     "hipaa privacy audit"),
        SettingsItem("Disclosure accounting", "compliance:disclosure_list", "Access and privacy",
                     "Disclosures of patient information to third parties.", is_admin,
                     "hipaa 164.528"),
        SettingsItem("Chain integrity", "audit:integrity", "Access and privacy",
                     "Verify the audit trail has not been altered.", is_manager,
                     "hash tamper verification", system=True),

        # ── Operations ───────────────────────────────────────────────────────
        SettingsItem("Workstations", "operations:workstation_list", "Operations",
                     "Benches and the instruments attached to them.", is_manager, "bench"),
        SettingsItem("Routing rules", "operations:routing_list", "Operations",
                     "Which bench a test is sent to.", is_manager, "assignment"),
        SettingsItem("Turnaround thresholds", "operations:tat_threshold_list", "Operations",
                     "Target, warning and breach times.", is_manager, "tat sla target"),
        SettingsItem("Worksheets", "operations:worksheet_list", "Operations",
                     "Batches of work grouped for a run.", is_lab, "batch run"),
        SettingsItem("Storage locations", "operations:storage_location_list", "Operations",
                     "Freezers, racks and boxes.", is_lab, "freezer rack box"),
        SettingsItem("Inventory", "inventory:item_list", "Operations",
                     "Reagents and consumables.", is_lab, "reagent stock consumable"),
        SettingsItem("Stock movements", "inventory:transaction_list", "Operations",
                     "Every restock and consumption.", is_lab, "reagent usage"),
        SettingsItem("Manufacturing recipes", "inventory:recipe_list", "Operations",
                     "Formulations for in-house media and reagents.", is_manager, "media"),
        SettingsItem("Production runs", "inventory:production_list", "Operations",
                     "Batches made in-house and their release.", is_lab, "batch media"),
        SettingsItem("Antibiotics", "specialty:antibiotic_list", "Operations",
                     "Agents reported on susceptibility panels.", is_manager, "micro ast"),

        # ── Reporting ────────────────────────────────────────────────────────
        SettingsItem("Controlled documents", "reporting:document_list", "Reporting",
                     "SOPs and policies under version control.", True, "sop policy manual"),
        SettingsItem("Requester registry", "reporting:requester_list", "Reporting",
                     "Clinicians, wards and clinics that send work.", is_manager,
                     "gp ward clinic referrer"),
        SettingsItem("Distribution rules", "reporting:distribution_list", "Reporting",
                     "How each requester's reports are delivered.", is_manager,
                     "email fax print delivery"),
        SettingsItem("Report delivery queue", "reporting:email_delivery", "Reporting",
                     "Outbound reports and their delivery status.", is_manager, "email outbox"),
        SettingsItem("Cumulative report", "reporting:cumulative", "Reporting",
                     "All results for one patient, trended.", is_lab, "trend history"),
        SettingsItem("Billing catalogue", "billing:item_list", "Reporting",
                     "Chargeable items and their prices.", is_manager, "price cpt charge"),
        SettingsItem("Invoices", "billing:invoice_list", "Reporting",
                     "Raised invoices and their balances.", is_lab, "charge payment"),

        # ── System ───────────────────────────────────────────────────────────
        SettingsItem("Instrument interfaces", "interop:interface_list", "System",
                     "Analyser connections and their code mappings.", is_manager,
                     "astm hl7 analyser middleware", system=True),
        SettingsItem("Instrument messages", "interop:message_list", "System",
                     "Raw traffic received from analysers.", is_manager, "astm hl7 log", system=True),
        SettingsItem("System alerts", "operations:alert_list", "System",
                     "Banners shown across the application.", is_manager, "banner notice", system=True),
        SettingsItem("Configuration", "operations:setting_list", "System",
                     "Key/value settings.", is_manager, "config", system=True),
        SettingsItem("Backup and maintenance", "operations:backup", "System",
                     "Operational procedures and audit health.", is_admin, "restore pg_dump", system=True),
        SettingsItem("Patient data administration", "patients:patient_admin_list", "System",
                     "Demographic corrections.", is_manager, "merge correct mrn"),
        SettingsItem("KPI dashboard", "operations:kpi", "System",
                     "Volume, turnaround and quality indicators.", is_manager,
                     "metrics statistics"),
        SettingsItem("Feedback", "operations:feedback", "System",
                     "Issues and suggestions raised by staff.", True, "bug suggestion"),
        SettingsItem("Epidemiology", "clinical:epidemiology", "System",
                     "Notifiable conditions detected and reported.", is_manager,
                     "public health surveillance"),
        SettingsItem("Tracking", "operations:tracking", "System",
                     "Specimen chain of custody.", True, "custody coc"),
        SettingsItem("Storage", "operations:storage", "System",
                     "Place a specimen into storage.", is_lab, "freezer"),
        SettingsItem("Queues", "operations:queues", "System",
                     "Work waiting in each authorisation queue.", is_lab, "workflow"),
    ]
    if is_installer:
        return [item for item in items if item.visible and item.system]
    return [item for item in items if item.visible]


def navigation(request):
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        return {}

    if user.is_installer:
        return {
            "nav_workspace": [i for i in _installer_workspace(user) if i.visible],
            "nav_oversight": [i for i in _installer_oversight(user) if i.visible],
            "nav_is_installer": True,
        }

    return {
        "nav_workspace": [item for item in _workspace(user) if item.visible],
        "nav_oversight": [item for item in _oversight(user) if item.visible],
        "nav_is_installer": False,
    }
