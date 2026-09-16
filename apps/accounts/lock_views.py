"""Lock endpoints and the lock administration screen."""
from __future__ import annotations

from django import forms
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts import locking
from apps.accounts.models import RecordLock
from apps.common.views import role_required

#: Entity types a lock may be taken on. A closed list, so a crafted request
#: cannot fill the table with locks on things that are not records.
LOCKABLE = {
    "patients.Patient": "Patient record",
    "laboratory.Order": "Order / specimen",
}


class BreakForm(forms.Form):
    reason = forms.CharField(
        label="Why are you breaking this lock?",
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text=(
            "Recorded in the audit trail against the record. "
            "'User has gone off shift with the record open' is a good reason; "
            "'needed it' is not."
        ),
    )


def _target(request):
    entity_type = (request.POST.get("entity_type") or "").strip()
    entity_id = (request.POST.get("entity_id") or "").strip()
    if entity_type not in LOCKABLE or not entity_id:
        return None, None
    return entity_type, entity_id


@require_POST
def heartbeat(request):
    """Keep an open screen's lock alive. Called on a timer by the page."""
    entity_type, entity_id = _target(request)
    if entity_type is None:
        return JsonResponse({"error": "unknown entity"}, status=400)

    held = locking.heartbeat(entity_type, entity_id, request.user)
    if held:
        return JsonResponse({"held": True})

    # The lock was lost — expired and taken, or broken by an administrator.
    # The page needs to know so it can stop offering a form that will refuse.
    lock = locking.current(entity_type, entity_id)
    return JsonResponse({
        "held": False,
        "holder": lock.username if lock else None,
    }, status=409)


@require_POST
def release(request):
    """Give up a lock. Sent by ``navigator.sendBeacon`` on leaving the page."""
    entity_type, entity_id = _target(request)
    if entity_type is None:
        return JsonResponse({"error": "unknown entity"}, status=400)
    locking.release(entity_type, entity_id, request.user)
    return JsonResponse({"released": True})


@role_required(*locking.BREAKER_ROLES)
def lock_list(request):
    """Every live lock, with the option to break one.

    Shown to managers, administrators and the installer. The installer sees
    which record type is locked and by whom, but not which record — an
    accession number or a patient key is an identifier, and unsticking the
    system does not require knowing whose record it is.
    """
    locks = (
        RecordLock.objects.filter(expires_at__gt=timezone.now())
        .select_related("user")
        .order_by("timestamp")
    )

    may_see_detail = request.user.may_see_patient_data
    rows = []
    for lock in locks:
        rows.append({
            "lock": lock,
            "kind": LOCKABLE.get(lock.entity_type, lock.entity_type),
            "label": _label_for(lock) if may_see_detail else "[redacted]",
        })

    return render(request, "accounts/lock_list.html", {
        "rows": rows,
        "form": BreakForm(),
        "may_see_detail": may_see_detail,
    })


def _label_for(lock: RecordLock) -> str:
    """A readable name for the locked record, for those permitted to see it."""
    if lock.entity_type == "laboratory.Order":
        from apps.laboratory.models import Order

        order = Order.objects.filter(pk=lock.entity_id).only("accession_number").first()
        return order.accession_number if order else lock.entity_id
    if lock.entity_type == "patients.Patient":
        from apps.patients.models import Patient

        patient = Patient.objects.filter(pk=lock.entity_id).only("mrn").first()
        return patient.mrn if patient else lock.entity_id
    return lock.entity_id


@require_POST
@role_required(*locking.BREAKER_ROLES)
def lock_break(request, pk):
    from apps.compliance.services import ControlViolation

    lock = get_object_or_404(RecordLock, pk=pk)
    form = BreakForm(request.POST)
    if not form.is_valid():
        messages.error(request, "A reason is required to break a lock.")
        return redirect("accounts:lock_list")

    holder = lock.username
    try:
        locking.break_lock(lock, by_user=request.user, reason=form.cleaned_data["reason"])
    except ControlViolation as violation:
        messages.error(request, str(violation))
    else:
        messages.success(
            request,
            f"Lock held by {holder} has been broken. If they are still in the "
            "record, their next save will be refused and they will be told why.",
        )
    return redirect("accounts:lock_list")
