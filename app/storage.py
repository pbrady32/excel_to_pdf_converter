"""Google Cloud Storage helpers."""

from __future__ import annotations

import os
from datetime import timedelta
from typing import Optional

from google.cloud import storage


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
        raise StorageError("Failed to upload PDF to storage") from exc


def signed_url(destination_path: str, expires_in: int = 3600) -> str:
    bucket_name = _get_bucket_name()
    client = _get_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_path)
    try:
        url = blob.generate_signed_url(expiration=timedelta(seconds=expires_in), method="GET")
        print("signed url", url)
    except Exception as exc:  # pragma: no cover
        logging.exception("Signed URL generation failed for %s", destination_path)
        raise StorageError(f"Failed to generate signed URL: {exc}") from exc
    return url


__all__ = ["upload_bytes", "signed_url", "StorageError"]
