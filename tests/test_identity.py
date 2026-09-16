"""Two-factor authentication and single sign-on.

The TOTP tests check against RFC 6238's own published vectors, so a change to
the implementation that still "works" but disagrees with every authenticator
app in existence is caught here rather than by a laboratory that cannot sign in.
"""
from __future__ import annotations

import base64
import json
import time
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts import mfa, sso
from apps.common.constants import Role
from tests.factories import make_user

PASSWORD = "Str0ng-Pass!23"
#: RFC 6238 Appendix B uses the ASCII string "12345678901234567890".
RFC_SECRET = base64.b32encode(b"12345678901234567890").decode().rstrip("=")


class TotpAlgorithmTests(TestCase):
    def test_rfc_6238_test_vectors(self):
        """Appendix B, SHA-1. Truncated to the low six digits."""
        for unix_time, expected in [
            (59, "287082"),
            (1111111109, "081804"),
            (1111111111, "050471"),
            (1234567890, "005924"),
            (2000000000, "279037"),
        ]:
            with self.subTest(t=unix_time):
                step = unix_time // mfa.STEP_SECONDS
                self.assertEqual(mfa.code_for(RFC_SECRET, step), expected)

    def test_a_generated_secret_is_valid_base32_of_the_right_length(self):
        secret = mfa.generate_secret()
        padded = secret + "=" * (-len(secret) % 8)
        self.assertEqual(len(base64.b32decode(padded)), mfa.SECRET_BYTES)

    def test_a_current_code_verifies(self):
        secret = mfa.generate_secret()
        now = time.time()
        code = mfa.code_for(secret, int(now // mfa.STEP_SECONDS))
        self.assertIsNotNone(mfa.verify_code(secret, code, when=now))

    def test_clock_drift_of_one_step_is_tolerated(self):
        secret = mfa.generate_secret()
        now = time.time()
        step = int(now // mfa.STEP_SECONDS)
        for offset in (-1, 0, 1):
            self.assertIsNotNone(
                mfa.verify_code(secret, mfa.code_for(secret, step + offset), when=now)
            )

    def test_drift_of_two_steps_is_not(self):
        secret = mfa.generate_secret()
        now = time.time()
        step = int(now // mfa.STEP_SECONDS)
        self.assertIsNone(
            mfa.verify_code(secret, mfa.code_for(secret, step + 2), when=now)
        )

    def test_a_used_step_cannot_be_replayed(self):
        secret = mfa.generate_secret()
        now = time.time()
        step = int(now // mfa.STEP_SECONDS)
        code = mfa.code_for(secret, step)

        self.assertEqual(mfa.verify_code(secret, code, when=now), step)
        self.assertIsNone(mfa.verify_code(secret, code, after_step=step, when=now))

    def test_rubbish_is_rejected_without_raising(self):
        secret = mfa.generate_secret()
        for presented in ["", "abc", "12345", "1234567", None, "   "]:
            self.assertIsNone(mfa.verify_code(secret, presented))

    def test_the_provisioning_uri_is_well_formed(self):
        uri = mfa.provisioning_uri("ABCDEF", username="jsmith")
        self.assertTrue(uri.startswith("otpauth://totp/"))
        self.assertIn("secret=ABCDEF", uri)
        self.assertIn("digits=6", uri)
        self.assertIn("period=30", uri)


class SecretStorageTests(TestCase):
    def test_a_secret_round_trips_through_encryption(self):
        secret = mfa.generate_secret()
        self.assertEqual(mfa.unseal(mfa.seal(secret)), secret)

    def test_the_stored_form_does_not_contain_the_secret(self):
        secret = mfa.generate_secret()
        self.assertNotIn(secret.encode(), mfa.seal(secret))


class RecoveryCodeTests(TestCase):
    def setUp(self):
        self.user = make_user("bms", password=PASSWORD)

    def test_codes_are_issued_and_stored_hashed(self):
        codes = mfa.issue_recovery_codes(self.user)
        self.assertEqual(len(codes), mfa.RECOVERY_CODE_COUNT)
        self.assertEqual(mfa.unused_recovery_code_count(self.user), len(codes))
        for stored in mfa.MfaRecoveryCode.objects.all():
            self.assertNotIn(stored.code_hash, codes)

    def test_a_code_works_exactly_once(self):
        codes = mfa.issue_recovery_codes(self.user)
        self.assertTrue(mfa.consume_recovery_code(self.user, codes[0]))
        self.assertFalse(mfa.consume_recovery_code(self.user, codes[0]))

    def test_regenerating_invalidates_the_previous_set(self):
        old = mfa.issue_recovery_codes(self.user)
        mfa.issue_recovery_codes(self.user)
        self.assertFalse(mfa.consume_recovery_code(self.user, old[0]))

    def test_another_users_code_does_not_work(self):
        codes = mfa.issue_recovery_codes(self.user)
        other = make_user("other", password=PASSWORD)
        self.assertFalse(mfa.consume_recovery_code(other, codes[0]))


class PolicyTests(TestCase):
    def test_admin_and_installer_require_a_second_factor_by_default(self):
        self.assertTrue(mfa.is_required_for(make_user("a", role=Role.ADMIN)))
        self.assertTrue(mfa.is_required_for(make_user("i", role=Role.INSTALLER)))

    def test_a_scientist_does_not(self):
        self.assertFalse(mfa.is_required_for(make_user("bms")))

    def test_it_can_be_turned_off_entirely(self):
        with self.settings(MFA_ENABLED=False):
            self.assertFalse(mfa.is_required_for(make_user("a", role=Role.ADMIN)))


def enrol(user) -> str:
    """Give a user a confirmed device and return the secret."""
    from django.utils import timezone

    secret = mfa.generate_secret()
    mfa.MfaDevice.objects.create(
        user=user, sealed_secret=mfa.seal(secret), confirmed_at=timezone.now()
    )
    return secret


def current_code(secret: str) -> str:
    return mfa.code_for(secret, int(time.time() // mfa.STEP_SECONDS))


class LoginFlowTests(TestCase):
    def setUp(self):
        self.user = make_user("bms", password=PASSWORD)

    def test_a_user_without_mfa_signs_in_in_one_step(self):
        response = self.client.post(
            reverse("accounts:login"), {"username": "bms", "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("mfa", response["Location"])
        self.assertIn("_auth_user_id", self.client.session)

    def test_an_enrolled_user_is_challenged_and_not_yet_signed_in(self):
        enrol(self.user)
        response = self.client.post(
            reverse("accounts:login"), {"username": "bms", "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/mfa/challenge/", response["Location"])
        # The crucial part: no session yet.
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_a_correct_code_completes_the_sign_in(self):
        secret = enrol(self.user)
        self.client.post(
            reverse("accounts:login"), {"username": "bms", "password": PASSWORD}
        )
        response = self.client.post(
            reverse("accounts:mfa_challenge"), {"code": current_code(secret)}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_a_wrong_code_does_not(self):
        enrol(self.user)
        self.client.post(
            reverse("accounts:login"), {"username": "bms", "password": PASSWORD}
        )
        self.client.post(reverse("accounts:mfa_challenge"), {"code": "000000"})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_the_challenge_cannot_be_reached_without_a_password_first(self):
        response = self.client.get(reverse("accounts:mfa_challenge"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login", response["Location"])

    def test_repeated_wrong_codes_throw_the_attempt_away(self):
        enrol(self.user)
        self.client.post(
            reverse("accounts:login"), {"username": "bms", "password": PASSWORD}
        )
        from apps.accounts.mfa_views import CHALLENGE_ATTEMPTS

        for _ in range(CHALLENGE_ATTEMPTS):
            response = self.client.post(
                reverse("accounts:mfa_challenge"), {"code": "000000"}
            )
        self.assertIn("/accounts/login", response["Location"])
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_a_recovery_code_completes_the_sign_in(self):
        enrol(self.user)
        codes = mfa.issue_recovery_codes(self.user)
        self.client.post(
            reverse("accounts:login"), {"username": "bms", "password": PASSWORD}
        )
        response = self.client.post(
            reverse("accounts:mfa_challenge"), {"code": codes[0]}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)
        self.assertEqual(
            mfa.unused_recovery_code_count(self.user), mfa.RECOVERY_CODE_COUNT - 1
        )

    def test_an_expired_challenge_sends_you_back(self):
        enrol(self.user)
        self.client.post(
            reverse("accounts:login"), {"username": "bms", "password": PASSWORD}
        )
        session = self.client.session
        session["_dx_mfa_since"] = time.time() - 3600
        session.save()

        response = self.client.get(reverse("accounts:mfa_challenge"))
        self.assertIn("/accounts/login", response["Location"])


class EnrolmentScreenTests(TestCase):
    def setUp(self):
        self.user = make_user("bms", password=PASSWORD)
        self.client.force_login(self.user)

    def test_setup_offers_a_key_and_does_not_yet_gate_sign_in(self):
        response = self.client.get(reverse("accounts:mfa_setup"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "otpauth://totp/")

        device = mfa.MfaDevice.objects.get(user=self.user)
        self.assertFalse(device.is_confirmed)
        self.assertIsNone(mfa.device_for(self.user))

    def test_confirming_with_a_correct_code_enrols_and_shows_recovery_codes(self):
        self.client.get(reverse("accounts:mfa_setup"))
        device = mfa.MfaDevice.objects.get(user=self.user)

        response = self.client.post(
            reverse("accounts:mfa_setup"), {"code": current_code(device.secret)}
        )
        self.assertContains(response, "Copy these now")
        self.assertIsNotNone(mfa.device_for(self.user))
        self.assertEqual(mfa.unused_recovery_code_count(self.user), mfa.RECOVERY_CODE_COUNT)

    def test_a_wrong_code_does_not_enrol(self):
        self.client.get(reverse("accounts:mfa_setup"))
        self.client.post(reverse("accounts:mfa_setup"), {"code": "000000"})
        self.assertIsNone(mfa.device_for(self.user))

    def test_disabling_requires_both_password_and_code(self):
        secret = enrol(self.user)
        self.client.post(reverse("accounts:mfa_disable"), {
            "password": "wrong", "code": current_code(secret),
        })
        self.assertIsNotNone(mfa.device_for(self.user))

        self.client.post(reverse("accounts:mfa_disable"), {
            "password": PASSWORD, "code": current_code(secret),
        })
        self.assertIsNone(mfa.device_for(self.user))

    def test_a_role_that_requires_mfa_cannot_disable_it(self):
        admin = make_user("admin1", role=Role.ADMIN, password=PASSWORD)
        secret = enrol(admin)
        self.client.force_login(admin)

        self.client.post(reverse("accounts:mfa_disable"), {
            "password": PASSWORD, "code": current_code(secret),
        })
        self.assertIsNotNone(mfa.device_for(admin))


# ── Single sign-on ───────────────────────────────────────────────────────────


DISCOVERY = {
    "issuer": "https://idp.example.org",
    "authorization_endpoint": "https://idp.example.org/authorize",
    "token_endpoint": "https://idp.example.org/token",
    "jwks_uri": "https://idp.example.org/jwks",
}

SSO_SETTINGS = dict(
    OIDC_ENABLED=True,
    OIDC_ISSUER="https://idp.example.org",
    OIDC_CLIENT_ID="dx-lis",
    OIDC_CLIENT_SECRET="s3cret",
    OIDC_REDIRECT_URI="https://lis.example.org/accounts/sso/callback/",
    OIDC_ROLE_CLAIM="groups",
    OIDC_ROLE_MAP={"lab-scientists": "scientist", "lab-admins": "admin"},
)


@override_settings(**SSO_SETTINGS)
class SsoConfigurationTests(TestCase):
    def test_it_is_enabled_when_configured(self):
        self.assertTrue(sso.is_enabled())

    def test_it_is_off_without_an_issuer(self):
        with self.settings(OIDC_ISSUER=""):
            self.assertFalse(sso.is_enabled())

    def test_the_login_page_offers_it(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertContains(response, "Sign in with")

    def test_the_login_page_does_not_when_it_is_off(self):
        with self.settings(OIDC_ENABLED=False):
            response = self.client.get(reverse("accounts:login"))
            self.assertNotContains(response, "Sign in with")


@override_settings(**SSO_SETTINGS)
class SsoFlowTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()

    def test_beginning_the_flow_redirects_with_pkce_state_and_nonce(self):
        with patch.object(sso, "_fetch_json", return_value=DISCOVERY):
            response = self.client.get(reverse("accounts:sso_begin"))

        self.assertEqual(response.status_code, 302)
        location = response["Location"]
        self.assertTrue(location.startswith("https://idp.example.org/authorize?"))
        for expected in ("code_challenge=", "code_challenge_method=S256",
                         "state=", "nonce=", "client_id=dx-lis"):
            self.assertIn(expected, location)

    def test_a_callback_with_a_wrong_state_is_refused(self):
        with patch.object(sso, "_fetch_json", return_value=DISCOVERY):
            self.client.get(reverse("accounts:sso_begin"))

        response = self.client.get(
            reverse("accounts:sso_callback"), {"code": "abc", "state": "not-the-state"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login", response["Location"])
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_a_callback_with_no_flow_in_progress_is_refused(self):
        response = self.client.get(
            reverse("accounts:sso_callback"), {"code": "abc", "state": "x"}
        )
        self.assertIn("/accounts/login", response["Location"])

    def test_a_provider_error_is_shown_rather_than_swallowed(self):
        response = self.client.get(reverse("accounts:sso_callback"), {
            "error": "access_denied", "error_description": "User cancelled",
        })
        self.assertIn("/accounts/login", response["Location"])


@override_settings(**SSO_SETTINGS)
class SsoTokenVerificationTests(TestCase):
    """Each of these checks has been a real-world OIDC vulnerability."""

    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        from cryptography.hazmat.primitives.asymmetric import rsa

        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        numbers = self.key.public_key().public_numbers()

        def b64(value: int) -> str:
            raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
            return base64.urlsafe_b64encode(raw).decode().rstrip("=")

        self.jwks = {"keys": [{
            "kty": "RSA", "kid": "test-key", "use": "sig", "alg": "RS256",
            "n": b64(numbers.n), "e": b64(numbers.e),
        }]}

    def _token(self, **claim_overrides) -> str:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        def encode(payload: dict) -> str:
            raw = json.dumps(payload).encode()
            return base64.urlsafe_b64encode(raw).decode().rstrip("=")

        header = encode({"alg": "RS256", "kid": "test-key", "typ": "JWT"})
        claims = {
            "iss": "https://idp.example.org",
            "aud": "dx-lis",
            "sub": "subject-1",
            "exp": time.time() + 300,
            "iat": time.time(),
            "nonce": "the-nonce",
            "preferred_username": "jsmith",
            "name": "J Smith",
            "email": "jsmith@example.org",
            "groups": ["lab-scientists"],
        }
        claims.update(claim_overrides)
        payload = encode(claims)
        signature = self.key.sign(
            f"{header}.{payload}".encode(), padding.PKCS1v15(), hashes.SHA256()
        )
        return f"{header}.{payload}.{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"

    def _verify(self, token, nonce="the-nonce"):
        with patch.object(sso, "discovery", return_value=DISCOVERY), \
             patch.object(sso, "jwks", return_value=self.jwks):
            return sso.verify_id_token(token, nonce=nonce)

    def test_a_good_token_verifies(self):
        claims = self._verify(self._token())
        self.assertEqual(claims["preferred_username"], "jsmith")

    def test_a_tampered_payload_is_rejected(self):
        header, payload, signature = self._token().split(".")
        forged = base64.urlsafe_b64encode(
            json.dumps({"sub": "someone-else"}).encode()
        ).decode().rstrip("=")
        with self.assertRaises(sso.SsoError):
            self._verify(f"{header}.{forged}.{signature}")

    def test_the_none_algorithm_is_rejected(self):
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "none"}).encode()
        ).decode().rstrip("=")
        _h, payload, _s = self._token().split(".")
        with self.assertRaises(sso.SsoError):
            self._verify(f"{header}.{payload}.")

    def test_a_token_for_another_audience_is_rejected(self):
        with self.assertRaises(sso.SsoError):
            self._verify(self._token(aud="some-other-app"))

    def test_a_token_from_another_issuer_is_rejected(self):
        with self.assertRaises(sso.SsoError):
            self._verify(self._token(iss="https://evil.example.org"))

    def test_an_expired_token_is_rejected(self):
        with self.assertRaises(sso.SsoError):
            self._verify(self._token(exp=time.time() - 3600))

    def test_a_replayed_nonce_is_rejected(self):
        with self.assertRaises(sso.SsoError):
            self._verify(self._token(nonce="a-different-nonce"))


@override_settings(**SSO_SETTINGS)
class SsoUserMappingTests(TestCase):
    def _claims(self, **overrides):
        claims = {
            "sub": "subject-1", "preferred_username": "jsmith",
            "name": "J Smith", "email": "jsmith@example.org",
            "groups": ["lab-scientists"],
        }
        claims.update(overrides)
        return claims

    def test_an_existing_account_is_matched_and_linked(self):
        existing = make_user("jsmith", password=PASSWORD)
        user, created = sso.resolve_user(self._claims())

        self.assertFalse(created)
        self.assertEqual(user.pk, existing.pk)
        user.refresh_from_db()
        self.assertEqual(user.sso_subject, "subject-1")

    def test_matching_prefers_the_subject_over_the_username(self):
        """People change their username; `sub` is the stable claim."""
        existing = make_user("old-name", password=PASSWORD)
        existing.sso_subject = "subject-1"
        existing.save(update_fields=["sso_subject"])

        user, _created = sso.resolve_user(self._claims(preferred_username="new-name"))
        self.assertEqual(user.pk, existing.pk)

    def test_an_unknown_user_is_refused_unless_provisioning_is_on(self):
        with self.assertRaises(sso.SsoError):
            sso.resolve_user(self._claims())

    def test_provisioning_creates_an_account_with_the_mapped_role(self):
        with self.settings(OIDC_PROVISION_USERS=True):
            user, created = sso.resolve_user(self._claims())
        self.assertTrue(created)
        self.assertEqual(user.role, "scientist")
        self.assertFalse(user.has_usable_password())

    def test_an_unmapped_group_is_refused_rather_than_guessed(self):
        with self.settings(OIDC_PROVISION_USERS=True):
            with self.assertRaises(sso.SsoError):
                sso.resolve_user(self._claims(groups=["some-other-group"]))

    def test_the_installer_role_is_never_granted_through_sso(self):
        with self.settings(
            OIDC_PROVISION_USERS=True,
            OIDC_ROLE_MAP={"it-admins": "installer"},
            OIDC_DEFAULT_ROLE="installer",
        ):
            self.assertIsNone(sso.role_for(self._claims(groups=["it-admins"])))
            with self.assertRaises(sso.SsoError):
                sso.resolve_user(self._claims(groups=["it-admins"]))

    def test_the_installer_account_cannot_sign_in_through_sso(self):
        """It is the break-glass account for when SSO is what has failed."""
        installer = make_user("installer", role=Role.INSTALLER, password=PASSWORD)
        with self.assertRaises(sso.SsoError):
            sso.resolve_user(self._claims(preferred_username=installer.username))

    def test_a_disabled_account_is_refused(self):
        user = make_user("jsmith", password=PASSWORD)
        user.is_active = False
        user.save(update_fields=["is_active"])
        with self.assertRaises(sso.SsoError):
            sso.resolve_user(self._claims())

    def test_claims_with_no_subject_are_refused(self):
        with self.assertRaises(sso.SsoError):
            sso.resolve_user({"preferred_username": "jsmith"})
