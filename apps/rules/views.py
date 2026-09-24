"""The rule builder, the approval step and the firing log."""
from __future__ import annotations

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.common.constants import LAB_STAFF_ROLES, MANAGEMENT_ROLES
from apps.common.views import (
    DxCreateView, DxDeleteView, DxListView, DxUpdateView, RoleRequiredMixin,
    role_required,
)
from apps.rules.forms import (
    ActionFormSet, ConditionFormSet, OverrideForm, RuleApprovalForm, RuleForm,
    SimulationForm,
)
from apps.rules.models import Rule, RuleExecution

MANAGERS = tuple(MANAGEMENT_ROLES)
LAB = tuple(LAB_STAFF_ROLES)


class RuleListView(DxListView):
    """Every rule with its live/draft state.

    ``status_label`` is shown rather than ``active``, because a rule can be
    enabled and still not firing — editing one withdraws its approval, and
    that distinction is the single most common source of "why did my rule not
    fire?".
    """

    model = Rule
    required_roles = LAB
    page_title = "Decision rules"
    page_subtitle = (
        "Interpretive comments, flags, reflex additions and automatic release — "
        "written by the laboratory, not by a programmer."
    )
    columns = [
        ("Name", "name", ""),
        ("Applies to", "test.code", "mono"),
        ("Trigger", "get_trigger_display", ""),
        ("Priority", "priority", "right"),
        ("Status", "status_label", ""),
    ]
    search_fields = ["name", "description"]
    filter_fields = {"trigger": "trigger"}
    create_url_name = "rules:rule_create"
    update_url_name = "rules:rule_update"
    delete_url_name = "rules:rule_delete"
    empty_message = "No rules yet. A new rule is a draft until somebody approves it."
    template_name = "rules/rule_list.html"
    prefetch_related = ("conditions", "actions")


class RuleFormMixin(RoleRequiredMixin):
    """Shared formset handling for the create and update screens."""

    model = Rule
    form_class = RuleForm
    required_roles = MANAGERS
    template_name = "rules/rule_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        instance = getattr(self, "object", None)
        if self.request.method == "POST":
            context["conditions"] = ConditionFormSet(
                self.request.POST, instance=instance, prefix="conditions"
            )
            context["actions"] = ActionFormSet(
                self.request.POST, instance=instance, prefix="actions"
            )
        else:
            context["conditions"] = ConditionFormSet(instance=instance, prefix="conditions")
            context["actions"] = ActionFormSet(instance=instance, prefix="actions")
        context["page_title"] = "Decision rule"
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        conditions, actions = context["conditions"], context["actions"]
        if not (conditions.is_valid() and actions.is_valid()):
            return self.render_to_response(context)

        with transaction.atomic():
            editing = form.instance.pk is not None
            if editing:
                # Any edit withdraws approval. A rule that keeps running on last
                # year's sign-off after being changed is the whole problem.
                form.instance.bump_version()
            self.object = form.save()
            conditions.instance = self.object
            conditions.save()
            actions.instance = self.object
            actions.save()

        if not self.object.conditions.exists():
            messages.warning(
                self.request,
                "This rule has no conditions, so it will match every result it "
                "is evaluated against. That is occasionally intended and usually "
                "is not — check before approving it.",
            )
        messages.success(
            self.request,
            f"Saved as version {self.object.version}. It will not fire until it is approved.",
        )
        return redirect("rules:rule_detail", pk=self.object.pk)


class RuleCreateView(RuleFormMixin, DxCreateView):
    pass


class RuleUpdateView(RuleFormMixin, DxUpdateView):
    pass


class RuleDeleteView(DxDeleteView):
    model = Rule
    required_roles = MANAGERS
    success_url = reverse_lazy("rules:rule_list")
    success_message = "Rule deleted. Its firing history is retained."


@role_required(*LAB)
def rule_detail(request, pk):
    """The rule in full, with its approval state and a simulation panel."""
    rule = get_object_or_404(
        Rule.objects.select_related("test", "department", "approved_by", "change_control")
        .prefetch_related("conditions", "actions", "actions__add_test"),
        pk=pk,
    )
    simulation = None
    form = SimulationForm(request.GET or None)

    if request.GET.get("accession_number") and form.is_valid():
        simulation = _simulate(rule, form.cleaned_data)

    return render(request, "rules/rule_detail.html", {
        "rule": rule,
        "conditions_by_group": _group(rule),
        "approval_form": RuleApprovalForm(),
        "simulation_form": form,
        "simulation": simulation,
        "recent": rule.executions.select_related("order")[:20]
        if request.user.may_see_patient_data else rule.executions.all()[:20],
        "can_approve": request.user.role in MANAGERS,
    })


def _group(rule) -> list[tuple[int, list]]:
    grouped: dict[int, list] = {}
    for condition in rule.conditions.all():
        grouped.setdefault(condition.group, []).append(condition)
    return sorted(grouped.items())


def _simulate(rule, data) -> dict:
    """Run a rule against a real order's results without changing anything."""
    from apps.laboratory.models import Order
    from apps.rules.engine import build_facts, simulate

    order = Order.objects.filter(accession_number=data["accession_number"]).first()
    if order is None:
        return {"error": f"No order with accession number {data['accession_number']}."}

    results = [row for row in order.results.select_related("test") if not row.is_report_row]
    if data.get("test_code"):
        results = [
            row for row in results
            if row.test is not None and row.test.code == data["test_code"]
        ]
    if not results:
        return {"error": "That order has no matching results to try the rule against."}

    trials = []
    for result in results:
        facts = build_facts(order, result.test, result)
        outcome = simulate(rule, facts)
        trials.append({
            "test_code": result.test.code if result.test_id else result.test_key,
            "value": result.value,
            **outcome,
        })
    return {"order": order, "trials": trials}


@require_POST
@role_required(*MANAGERS)
def rule_approve(request, pk):
    """Sign a rule into service.

    Approval is an electronic signature because a rule decides what a report
    says. CLIA §493.1253 treats a change to the examination process as
    something requiring validation and authorisation; this is where that is
    recorded.
    """
    from apps.compliance.models import ElectronicSignature
    from apps.compliance.services import ControlViolation, apply_signature

    rule = get_object_or_404(Rule, pk=pk)
    if request.user.role not in MANAGERS:
        messages.error(request, "Only a manager or administrator may approve a rule.")
        return redirect("rules:rule_detail", pk=rule.pk)

    form = RuleApprovalForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Record what was reviewed before approving.")
        return redirect("rules:rule_detail", pk=rule.pk)

    if rule.has_auto_verify and not (rule.test and rule.test.auto_verify_permitted):
        messages.warning(
            request,
            "This rule asks for automatic verification, but the analyte it "
            "targets is not approved for it. Enable 'auto verify permitted' on "
            "the test definition, or the rule will be refused at run time.",
        )

    try:
        signature = apply_signature(
            user=request.user,
            meaning=ElectronicSignature.Meaning.REVIEW,
            entity_type="rules.Rule",
            entity_id=rule.pk,
            payload={
                "rule": rule.name,
                "version": rule.version,
                "summary": rule.summary(),
            },
            password=form.cleaned_data.get("password"),
            comment=form.cleaned_data["comment"],
            request=request,
        )
    except ControlViolation as violation:
        messages.error(request, str(violation))
        return redirect("rules:rule_detail", pk=rule.pk)

    rule.approved_by = request.user
    rule.approved_at = timezone.now()
    rule.approved_version = rule.version
    rule.save(update_fields=["approved_by", "approved_at", "approved_version"])

    messages.success(
        request,
        f"Version {rule.version} approved and live. Signed: {signature.manifest}",
    )
    return redirect("rules:rule_detail", pk=rule.pk)


class ExecutionListView(DxListView):
    """Every rule firing, newest first."""

    model = RuleExecution
    required_roles = LAB
    page_title = "Rule firing log"
    page_subtitle = "What the rules did, to which result, and on what facts."
    search_fields = ["rule_name", "test_code"]
    filter_fields = {"outcome": "outcome", "rule": "rule_id"}
    template_name = "rules/execution_list.html"

    CLINICAL_COLUMNS = [
        ("Fired", "fired_at", "nowrap"),
        ("Rule", "rule_name", ""),
        ("Accession", "order.accession_number", "mono"),
        ("Test", "test_code", "mono"),
        ("Outcome", "get_outcome_display", ""),
        ("Autoverified", "auto_verified", ""),
    ]
    REDACTED_COLUMNS = [
        ("Fired", "fired_at", "nowrap"),
        ("Rule", "rule_name", ""),
        ("Specimen", "safe_test_code", "muted"),
        ("Outcome", "get_outcome_display", ""),
        ("Facts", "safe_facts", "muted"),
    ]

    @property
    def columns(self):
        if self.request.user.may_see_patient_data:
            return self.CLINICAL_COLUMNS
        return self.REDACTED_COLUMNS


@role_required(*LAB)
def execution_detail(request, pk):
    """One firing: the facts the rule saw, what it did, and any refusals.

    This is the screen that answers "why does this report say that?". The facts
    are redacted for roles barred from patient data — an age, a sex, a
    diagnosis code and an analyte value together identify somebody.
    """
    execution = get_object_or_404(
        RuleExecution.objects.select_related("rule", "order", "result", "signature", "overridden_by"),
        pk=pk,
    )
    return render(request, "rules/execution_detail.html", {
        "execution": execution,
        "override_form": OverrideForm(),
        "can_override": (
            execution.auto_verified
            and not execution.is_overridden
            and request.user.role in LAB
        ),
        "facts": sorted((execution.facts or {}).items()),
    })


@require_POST
@role_required(*LAB)
def execution_override(request, pk):
    """Take an autoverified result back for a person to look at."""
    from apps.compliance.services import ControlViolation
    from apps.rules.autoverify import override

    execution = get_object_or_404(RuleExecution, pk=pk)
    form = OverrideForm(request.POST)
    if not form.is_valid():
        messages.error(request, "A reason is required.")
        return redirect("rules:execution_detail", pk=execution.pk)

    try:
        override(execution, user=request.user, reason=form.cleaned_data["reason"])
    except ControlViolation as violation:
        messages.error(request, str(violation))
    else:
        messages.success(
            request,
            "The result has been returned to the worklist for human verification.",
        )
    return redirect("rules:execution_detail", pk=execution.pk)
