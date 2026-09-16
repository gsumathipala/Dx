"""OpenID Connect single sign-on.

Why OIDC and not SAML or LDAP
-----------------------------
Every hospital identity platform in current use — Entra ID, Okta, Keycloak,
Ping — speaks OIDC. SAML would need XML signature verification, which is a
notoriously sharp-edged thing to implement and a genuinely bad idea to write
by hand. LDAP would need a binary protocol library and a direct route from the
application to the directory, which most hospital networks do not want.

OIDC is an HTTPS redirect and a signed token. It is implementable correctly
with what is already here, so it is implemented here.

What is implemented
-------------------
Authorization Code flow with PKCE (RFC 7636), ``state`` for CSRF and ``nonce``
for token replay, discovery via ``.well-known/openid-configuration``, and ID
token verification against the issuer's JWKS using RS256.

Every one of those is load-bearing:

* **PKCE** stops an intercepted authorization code being redeemed by anybody
  but the client that started the flow.
* **state** is the only thing standing between this and a login-CSRF, where an
  attacker completes a flow that signs you into *their* account.
* **nonce** binds the ID token to this particular authentication, so an old
  token cannot be replayed.
* **Signature, issuer, audience and expiry** are all checked. An unverified ID
  token is a bearer assertion from whoever sent it.

What is deliberately not implemented
------------------------------------
* **Just-in-time role escalation.** The identity provider says who somebody
  is. What they may do here is decided here, from an explicit claim-to-role
  map with a conservative default. A directory group rename must not silently
  grant clinical authority.
* **The installer account.** It is never provisioned or authenticated through
  SSO. It is the break-glass account for the case where SSO itself is broken,
  which is exactly when it is needed.
* **Back-channel logout.** Sessions here already expire on idle timeout; a
  half-implemented logout channel would be worse than none.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger("dx.sso")

DISCOVERY_CACHE_SECONDS = 3600
JWKS_CACHE_SECONDS = 3600
HTTP_TIMEOUT = 10


class SsoError(Exception):
    """Anything that stops a sign-in. The message is shown to the user."""


class SsoNotConfigured(SsoError):
    pass


# ── Configuration ────────────────────────────────────────────────────────────


def is_enabled() -> bool:
    return bool(
        getattr(settings, "OIDC_ENABLED", False)
        and getattr(settings, "OIDC_ISSUER", "")
        and getattr(settings, "OIDC_CLIENT_ID", "")
    )


def _setting(name: str, default=None):
    value = getattr(settings, name, default)
    if value in (None, ""):
        raise SsoNotConfigured(f"{name} is not set.")
    return value


def provider_name() -> str:
    return getattr(settings, "OIDC_PROVIDER_NAME", "your organisation account")


# ── Discovery and keys ───────────────────────────────────────────────────────


def _fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise SsoError(f"The identity provider returned {error.code} for {url}.")
    except Exception as error:
        raise SsoError(f"The identity provider could not be reached: {error}")


def discovery() -> dict:
    issuer = _setting("OIDC_ISSUER").rstrip("/")
    key = f"dx:oidc:discovery:{hashlib.sha256(issuer.encode()).hexdigest()[:16]}"
    document = cache.get(key)
    if document is None:
        document = _fetch_json(f"{issuer}/.well-known/openid-configuration")
        for required in ("authorization_endpoint", "token_endpoint", "jwks_uri", "issuer"):
            if required not in document:
                raise SsoError(f"The provider's discovery document has no {required}.")
        cache.set(key, document, DISCOVERY_CACHE_SECONDS)
    return document


def jwks() -> dict:
    uri = discovery()["jwks_uri"]
    key = f"dx:oidc:jwks:{hashlib.sha256(uri.encode()).hexdigest()[:16]}"
    keys = cache.get(key)
    if keys is None:
        keys = _fetch_json(uri)
        cache.set(key, keys, JWKS_CACHE_SECONDS)
    return keys


# ── JWT verification ─────────────────────────────────────────────────────────


def _b64url(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _public_key(kid: str | None):
    """Find the signing key and build an RSA public key from its JWK."""
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers

    candidates = [
        key for key in jwks().get("keys", [])
        if key.get("kty") == "RSA" and (kid is None or key.get("kid") == kid)
    ]
    if not candidates:
        # The provider may have rotated keys since the cache was filled.
        cache.delete(
            f"dx:oidc:jwks:{hashlib.sha256(discovery()['jwks_uri'].encode()).hexdigest()[:16]}"
        )
        candidates = [
            key for key in jwks().get("keys", [])
            if key.get("kty") == "RSA" and (kid is None or key.get("kid") == kid)
        ]
    if not candidates:
        raise SsoError("The token was signed with a key the provider does not publish.")

    jwk = candidates[0]
    modulus = int.from_bytes(_b64url(jwk["n"]), "big")
    exponent = int.from_bytes(_b64url(jwk["e"]), "big")
    return RSAPublicNumbers(exponent, modulus).public_key()


def verify_id_token(token: str, *, nonce: str, leeway: int = 60) -> dict:
    """Verify signature, issuer, audience, expiry and nonce. Returns the claims.

    Every check here has been the subject of a real-world OIDC vulnerability.
    Skipping any one of them turns the token into an unauthenticated assertion
    from whoever sent it.
    """
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError:
        raise SsoError("The identity provider returned a malformed token.")

    header = json.loads(_b64url(header_b64))
    claims = json.loads(_b64url(payload_b64))

    algorithm = header.get("alg")
    if algorithm != "RS256":
        # "none" and HMAC confusion are the two classic JWT attacks; an
        # allow-list of one algorithm closes both.
        raise SsoError(f"Unsupported token signing algorithm {algorithm!r}.")

    try:
        _public_key(header.get("kid")).verify(
            _b64url(signature_b64),
            f"{header_b64}.{payload_b64}".encode("ascii"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except InvalidSignature:
        raise SsoError("The token's signature did not verify.")

    expected_issuer = discovery()["issuer"].rstrip("/")
    if str(claims.get("iss", "")).rstrip("/") != expected_issuer:
        raise SsoError("The token was issued by a different provider.")

    audience = claims.get("aud")
    audiences = audience if isinstance(audience, list) else [audience]
    if _setting("OIDC_CLIENT_ID") not in audiences:
        raise SsoError("The token was issued for a different application.")

    now = time.time()
    if float(claims.get("exp", 0)) < now - leeway:
        raise SsoError("The token has expired.")
    if float(claims.get("iat", now)) > now + leeway:
        raise SsoError("The token was issued in the future; check clock sync.")

    if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
        raise SsoError("The token does not match this sign-in attempt.")

    return claims


# ── The flow ─────────────────────────────────────────────────────────────────


def begin(request, *, next_url: str = "") -> str:
    """Start the flow. Returns the URL to send the browser to."""
    if not is_enabled():
        raise SsoNotConfigured("Single sign-on is not configured.")

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)[:128]
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).decode("ascii").rstrip("=")

    request.session["_dx_sso"] = {
        "state": state, "nonce": nonce, "verifier": verifier,
        "started": time.time(), "next": next_url,
    }

    query = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": _setting("OIDC_CLIENT_ID"),
        "redirect_uri": _setting("OIDC_REDIRECT_URI"),
        "scope": getattr(settings, "OIDC_SCOPES", "openid profile email"),
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    return f"{discovery()['authorization_endpoint']}?{query}"


def exchange(request, *, code: str, state: str) -> dict:
    """Redeem the authorization code and return the verified claims."""
    stored = request.session.pop("_dx_sso", None)
    if not stored:
        raise SsoError("There is no sign-in in progress. Start again.")
    if time.time() - stored["started"] > 600:
        raise SsoError("That sign-in took too long. Start again.")
    if not hmac.compare_digest(stored["state"], state or ""):
        # Without this check an attacker can complete a flow that signs the
        # victim into the attacker's account.
        raise SsoError("The sign-in could not be verified. Start again.")

    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": _setting("OIDC_REDIRECT_URI"),
        "client_id": _setting("OIDC_CLIENT_ID"),
        "client_secret": getattr(settings, "OIDC_CLIENT_SECRET", ""),
        "code_verifier": stored["verifier"],
    }).encode("ascii")

    token_request = urllib.request.Request(
        discovery()["token_endpoint"], data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(token_request, timeout=HTTP_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:200]
        logger.warning("OIDC token exchange failed (%s): %s", error.code, detail)
        raise SsoError("The identity provider rejected the sign-in.")
    except Exception as error:
        raise SsoError(f"The identity provider could not be reached: {error}")

    if "id_token" not in payload:
        raise SsoError("The identity provider returned no ID token.")

    return verify_id_token(payload["id_token"], nonce=stored["nonce"])


# ── Mapping claims onto an account ───────────────────────────────────────────


def role_for(claims: dict) -> str | None:
    """Map the provider's groups onto a Dx role.

    Explicit and conservative. ``OIDC_ROLE_MAP`` maps a group value to a role;
    anything unmapped gets ``OIDC_DEFAULT_ROLE``, which defaults to None —
    meaning the sign-in is refused rather than guessed at. A directory group
    rename must not silently grant clinical authority, and an unknown group
    must not default to something useful.

    The installer role is never granted here at all.
    """
    from apps.common.constants import Role

    claim_name = getattr(settings, "OIDC_ROLE_CLAIM", "groups")
    mapping = {str(k): str(v) for k, v in getattr(settings, "OIDC_ROLE_MAP", {}).items()}

    raw = claims.get(claim_name)
    values = raw if isinstance(raw, list) else ([raw] if raw else [])

    for value in values:
        mapped = mapping.get(str(value))
        if mapped and mapped != Role.INSTALLER:
            return mapped

    default = getattr(settings, "OIDC_DEFAULT_ROLE", None)
    return default if default and default != Role.INSTALLER else None


def resolve_user(claims: dict):
    """Find or create the local account for these claims.

    Matching is on ``sub`` where we have seen it before, falling back to
    username. ``sub`` is the only claim the provider guarantees is stable —
    email addresses and usernames change when people marry, and matching on
    them would silently hand one person another's record.
    """
    from django.contrib.auth import get_user_model

    from apps.common.constants import Role

    User = get_user_model()

    subject = claims.get("sub")
    if not subject:
        raise SsoError("The identity provider returned no subject identifier.")

    username = (
        claims.get(getattr(settings, "OIDC_USERNAME_CLAIM", "preferred_username"))
        or claims.get("email")
        or subject
    )
    username = str(username).strip().lower()

    existing = User.objects.filter(sso_subject=subject).first()
    if existing is None:
        existing = User.objects.filter(username__iexact=username).first()

    if existing is not None:
        if existing.is_installer:
            # The break-glass account is local-only by design: it exists for
            # the case where SSO itself is what has failed.
            raise SsoError(
                "The installer account cannot sign in through single sign-on. "
                "Use its local password."
            )
        if not existing.is_active:
            raise SsoError("That account is disabled.")

        changed = []
        if existing.sso_subject != subject:
            existing.sso_subject = subject
            changed.append("sso_subject")
        full_name = claims.get("name")
        if full_name and existing.name != full_name:
            existing.name = full_name
            changed.append("name")
        email = claims.get("email")
        if email and existing.email != email:
            existing.email = email
            changed.append("email")
        if changed:
            existing.save(update_fields=changed)
        return existing, False

    if not getattr(settings, "OIDC_PROVISION_USERS", False):
        raise SsoError(
            f"There is no {username!r} account here. Ask an administrator to "
            "create one before signing in with single sign-on."
        )

    role = role_for(claims)
    if role is None:
        raise SsoError(
            "Your account has no role in this laboratory system. Ask an "
            "administrator to grant one."
        )
    if role == Role.INSTALLER:  # pragma: no cover - role_for already refuses
        raise SsoError("The installer role cannot be granted through single sign-on.")

    user = User.objects.create_user(
        username=username,
        password=None,  # unusable: this account authenticates through the IdP
        name=claims.get("name") or username,
        email=claims.get("email") or "",
        role=role,
        sso_subject=subject,
    )
    user.set_unusable_password()
    user.save(update_fields=["password"])
    return user, True
