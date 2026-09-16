"""Authentication and user administration."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from apps.accounts.forms import CompetencyForm, DepartmentForm, UserForm
from apps.accounts.models import Department, UserCompetency
from apps.common.constants import MANAGEMENT_ROLES, SYSTEM_ROLES, Role
from apps.common.views import DxCreateView, DxDeleteView, DxListView, DxUpdateView

User = get_user_model()

ADMIN_ONLY = (Role.ADMIN,)
MANAGERS = tuple(MANAGEMENT_ROLES)
#: Account and department administration: the installer's core responsibility.
SYSTEM = tuple(SYSTEM_ROLES)


class DxLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def get_form_class(self):
        from apps.accounts.forms import DxLoginForm

        return DxLoginForm

    def get_context_data(self, **kwargs):
        from apps.accounts import sso

        context = super().get_context_data(**kwargs)
        context["sso_enabled"] = sso.is_enabled()
        context["sso_provider"] = sso.provider_name()
        return context

    def form_valid(self, form):
        """Password accepted — but not necessarily signed in.

        Where a second factor applies, ``login()`` is deliberately not called
        here. The user has no session until the code is verified; a
        half-finished sign-in that already carried a session would be one
        factor wearing the costume of two.
        """
        from apps.accounts import mfa
        from apps.accounts.mfa_views import begin_challenge

        user = form.get_user()
        if mfa.device_for(user) or mfa.is_required_for(user):
            begin_challenge(self.request, user)
            destination = reverse_lazy("accounts:mfa_challenge")
            next_url = self.request.POST.get("next") or self.request.GET.get("next")
            return redirect(f"{destination}?next={next_url}" if next_url else destination)

        return super().form_valid(form)


class DxLogoutView(LogoutView):
    """Sign out, releasing anything the user still has open.

    Without this, a scientist who finishes a shift with a result-entry screen
    open leaves the order locked for the next fifteen minutes, and the night
    shift learns to break locks as a matter of routine — which is how a
    control stops being one.
    """

    next_page = reverse_lazy("accounts:login")

    def dispatch(self, request, *args, **kwargs):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            from apps.accounts import locking

            locking.release_all_for(user)
        return super().dispatch(request, *args, **kwargs)


# ── Users ────────────────────────────────────────────────────────────────────


# ── Departments ──────────────────────────────────────────────────────────────


# ── Competency (CLIA §493.1451) ──────────────────────────────────────────────


# ── Account administration ───────────────────────────────────────────────────


def _may_administer_users(user) -> bool:
    return user.is_authenticated and (user.is_admin or user.is_installer)


@login_required
@user_passes_test(_may_administer_users)
def reset_password(request, pk):
    """Issue a temporary password that the holder must change at first use.

    The administrator never learns the colleague's working password: the
    temporary one is single-use by construction, because
    ``must_change_password`` forces a change before anything else can be done.
    """
    from apps.accounts.forms import AdminPasswordResetForm
    from apps.audit.recorder import record
    from apps.common.constants import AuditAction
    from apps.compliance.services import record_password_change, security_state

    target = get_object_or_404(User, pk=pk)

    allowed, refusal = target.may_have_password_reset_by(request.user)
    if not allowed:
        messages.error(request, refusal)
        return redirect("accounts:user_list")

    form = AdminPasswordResetForm(target, request.POST or None)
    if request.method == "POST" and form.is_valid():
        target.set_password(form.cleaned_data["new_password"])
        target.save(update_fields=["password"])
        record_password_change(target)

        state = security_state(target)
        state.must_change_password = True
        state.failed_attempts = 0
        state.locked_until = None
        state.save(update_fields=["must_change_password", "failed_attempts", "locked_until"])

        record(
            action=AuditAction.UPDATE,
            entity_type="accounts.User",
            entity_id=target.pk,
            entity_label=f"password reset by administrator: {target.username}",
            changes={"password": {"old": "********", "new": "********"},
                     "must_change_password": {"old": False, "new": True}},
            reason=form.cleaned_data["reason"],
            blocking=True,
        )
        messages.success(
            request,
            f"Temporary password set for {target.username}. They must change it "
            "when they next sign in.",
        )
        return redirect("accounts:user_list")

    return render(request, "accounts/reset_password.html", {"target": target, "form": form})


@login_required
@user_passes_test(_may_administer_users)
@require_POST
def toggle_active(request, pk):
    """Enable or disable an account, including the installer's.

    Disabling is the control that lets a laboratory shut out any account —
    including the permanent installer account — without being able to take it
    over.
    """
    from apps.audit.recorder import record
    from apps.common.constants import AuditAction

    target = get_object_or_404(User, pk=pk)

    if target.pk == request.user.pk:
        messages.error(request, "You cannot disable your own account.")
        return redirect("accounts:user_list")

    target.is_active = not target.is_active
    target.save(update_fields=["is_active"])

    record(
        action=AuditAction.UPDATE,
        entity_type="accounts.User",
        entity_id=target.pk,
        entity_label=f"account {'enabled' if target.is_active else 'disabled'}: {target.username}",
        changes={"is_active": {"old": not target.is_active, "new": target.is_active}},
        reason=request.POST.get("reason") or None,
        blocking=True,
    )

    if target.is_active:
        messages.success(request, f"{target.username} re-enabled.")
    else:
        messages.warning(
            request,
            f"{target.username} disabled. They cannot sign in until re-enabled. "
            "Their existing records are untouched.",
        )
    return redirect("accounts:user_list")


@login_required
@user_passes_test(_may_administer_users)
def delete_user(request, pk):
    """Remove an account, if nothing depends on it.

    An account that has signed results cannot be deleted — the signature has to
    keep naming a real person. In that case the account is disabled instead,
    which is what "removing" someone means in a regulated system.
    """
    from django.db.models import ProtectedError

    target = get_object_or_404(User, pk=pk)

    allowed, refusal = target.may_be_deleted_by(request.user)
    if not allowed:
        messages.error(request, refusal)
        return redirect("accounts:user_list")

    if request.method == "POST":
        username = target.username
        try:
            target.delete()
        except ProtectedError:
            target.is_active = False
            target.save(update_fields=["is_active"])
            messages.warning(
                request,
                f"{username} has signed or authorised records, so the account "
                "cannot be deleted — those records must keep naming a real "
                "person. The account has been disabled instead.",
            )
        else:
            messages.success(request, f"{username} deleted.")
        return redirect("accounts:user_list")

    return render(request, "accounts/confirm_delete_user.html", {"target": target})
