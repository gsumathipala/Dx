"""Authentication backend that understands legacy credentials."""
from __future__ import annotations

import logging

import bcrypt
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

logger = logging.getLogger("dx.accounts")


class LegacyCompatibleBackend(ModelBackend):
    """Authenticate against Django hashes, bcrypt hashes, or a legacy cleartext row.

    The Next.js implementation stored bcrypt hashes (``$2a``/``$2b``/``$2y``
    prefixes) and, for un-migrated seed rows, cleartext. Both are accepted once
    and immediately rewritten as a Django hash, so the legacy formats disappear
    as users sign in.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(username=username)
        except UserModel.DoesNotExist:
            # Equalise timing so a missing username is indistinguishable from
            # a wrong password.
            UserModel().set_password(password)
            return None

        from apps.compliance.services import (
            check_account_available,
            register_failed_login,
            register_successful_login,
        )

        if not check_account_available(user).allowed:
            return None

        if self._verify(user, password) and self.user_can_authenticate(user):
            register_successful_login(user)
            return user

        register_failed_login(username)
        return None

    def _verify(self, user, password: str) -> bool:
        stored = user.password or ""

        if stored.startswith(("$2a$", "$2b$", "$2y$")):
            try:
                ok = bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
            except ValueError:
                ok = False
            if ok:
                self._upgrade(user, password, "bcrypt")
            return ok

        if user.check_password(password):
            return True

        # Legacy cleartext row: accept once, then upgrade.
        if stored and stored == password:
            logger.warning("Upgrading cleartext password for user %s", user.username)
            self._upgrade(user, password, "cleartext")
            return True

        return False

    @staticmethod
    def _upgrade(user, password: str, previous_format: str) -> None:
        from apps.audit.context import suppress_auditing
        from apps.audit.recorder import record
        from apps.common.constants import AuditAction
        from apps.compliance.services import record_password_change

        user.set_password(password)
        # The raw UPDATE would otherwise emit a field-level diff containing the
        # masked password; one explicit event is clearer.
        with suppress_auditing():
            user.save(update_fields=["password"])
        record_password_change(user)
        record(
            action=AuditAction.UPDATE,
            entity_type="accounts.User",
            entity_id=user.pk,
            entity_label=f"password rehashed: {user.username}",
            changes={"password_format": {"old": previous_format, "new": "django"}},
            blocking=True,
        )
