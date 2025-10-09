"""Firebase Identity Platform authentication helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Optional

import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials


class AuthError(Exception):
    """Raised when identity verification fails."""


@dataclass(frozen=True)
class AuthContext:
    """Represents a verified user identity."""

    uid: str
    email: Optional[str]
    claims: dict


_app: Optional[firebase_admin.App] = None
_allowed_domains: Optional[set[str]] = None


def _parse_allowed_domains(value: Optional[str]) -> Optional[set[str]]:
    if not value:
        return None
    domains: set[str] = set()
    for raw in value.split(","):
        cleaned = raw.strip().lower()
        if cleaned:
            domains.add(cleaned)
    return domains or None


def _load_allowed_domains() -> Optional[set[str]]:
    global _allowed_domains
    if _allowed_domains is None:
        _allowed_domains = _parse_allowed_domains(os.environ.get("FIREBASE_ALLOWED_EMAIL_DOMAINS"))
    return _allowed_domains


def _initialize_app() -> firebase_admin.App:
    global _app
    if _app is not None:
        return _app

    if firebase_admin._apps:
        _app = firebase_admin.get_app()
        return _app

    cred: credentials.Base
    credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if credentials_path and os.path.exists(credentials_path):
        cred = credentials.Certificate(credentials_path)
    else:
        cred = credentials.ApplicationDefault()

    options = {}
    project_id = os.environ.get("FIREBASE_PROJECT_ID")
    if project_id:
        options["projectId"] = project_id

    _app = firebase_admin.initialize_app(cred, options or None)
    return _app


def _enforce_domain(email: Optional[str], allowed: Optional[Iterable[str]]) -> None:
    if not allowed or not email:
        return
    domain = email.split("@")[-1].lower()
    if domain not in allowed:
        raise AuthError(f"Email domain '{domain}' is not allowed")


def verify_token(id_token: str) -> AuthContext:
    """Verify an ID token using Firebase Admin SDK and optional domain allowlist."""

    if not id_token:
        raise AuthError("Missing Authorization token")

    app = _initialize_app()
    try:
        decoded = firebase_auth.verify_id_token(id_token, app=app)
    except firebase_auth.InvalidIdTokenError as exc:  # type: ignore[attr-defined]
        raise AuthError("Invalid ID token") from exc
    except firebase_auth.ExpiredIdTokenError as exc:  # type: ignore[attr-defined]
        raise AuthError("Expired ID token") from exc
    except firebase_auth.RevokedIdTokenError as exc:  # type: ignore[attr-defined]
        raise AuthError("Revoked ID token") from exc
    except Exception as exc:  # pragma: no cover - unexpected errors surfaced to caller
        raise AuthError("Failed to verify ID token") from exc

    email = decoded.get("email")
    _enforce_domain(email, _load_allowed_domains())

    return AuthContext(uid=decoded["uid"], email=email, claims=decoded)


__all__ = ["AuthContext", "AuthError", "verify_token"]
