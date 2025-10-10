"""Google Cloud Storage helpers."""

from __future__ import annotations

import os
import logging
from datetime import timedelta

import google.auth
from google.auth.transport.requests import Request
from google.cloud import storage

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Raised when storage interactions fail."""

def _get_bucket_name() -> str:
    bucket = os.environ.get("OUTPUT_BUCKET")
    if not bucket:
        raise StorageError("OUTPUT_BUCKET environment variable is not set")
    return bucket


def _get_client() -> storage.Client:
    try:
        return storage.Client()
    except Exception as exc:  # pragma: no cover - let caller handle
        raise StorageError("Failed to initialize storage client") from exc


def upload_bytes(data: bytes, destination_path: str, content_type: str = "application/pdf") -> None:
    bucket_name = _get_bucket_name()
    client = _get_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_path)
    try:
        blob.upload_from_string(data, content_type=content_type)
    except Exception as exc:  # pragma: no cover - let caller handle
        logger.exception("Upload failed for %s", destination_path)
        raise StorageError("Failed to upload PDF to storage") from exc


def signed_url(destination_path: str, expires_in: int = 3600) -> str:
    bucket_name = _get_bucket_name()

    # We only specify the credentials if we are running locally
    # Otherwise, we use the service account attached to the Cloud Run service
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        pass
    else:
        # Get ADC (Cloud Run’s attached service account) and refresh to obtain an access token
        credentials, _ = google.auth.default()
        credentials.refresh(Request())
    
        # Prefer explicit env var; fall back to credentials attr if present
        signer_email = os.environ.get("SIGNING_SERVICE_ACCOUNT") or getattr(credentials, "service_account_email", None)
        if not signer_email:
            raise RuntimeError("Set SIGNING_SERVICE_ACCOUNT to the signer service account email")

    client = _get_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_path)
    try:
        if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(seconds=expires_in),
                method="GET",
            )
        else:
        # This path uses IAM signBlob (no local private key needed)
            url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expires_in),
            method="GET",
            service_account_email=signer_email,
            access_token=credentials.token,
            )
    except Exception as exc:  # pragma: no cover
        logger.exception("Signed URL generation failed for %s", destination_path)
        raise StorageError(f"Failed to generate signed URL: {exc}") from exc
    return url


__all__ = ["upload_bytes", "signed_url", "StorageError"]
