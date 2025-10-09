"""Excel parsing utilities for client worksheet generation."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Iterable, List, Optional, Tuple
TAX_YEAR_PATTERN = re.compile(r"^\d{4}$")


import pandas as pd


class ExcelParsingError(Exception):
    """Raised when we cannot parse the expected data from an Excel file."""


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().split())


def _find_client_name(df: pd.DataFrame) -> str:
    """Locate the client name by scanning the top rows for a label."""

    max_scan_rows = min(10, len(df))
    fallback: Optional[str] = None

    for row_idx in range(max_scan_rows):
        row = df.iloc[row_idx]
        for col_idx, raw in enumerate(row):
            if pd.isna(raw):
                continue
            text = str(raw).strip()
            if not text:
                continue
            normalized = _normalize_text(text)
            lowered = normalized.lower()

            if "name" in lowered and "client" in lowered:
                # Try to read the next non-empty cell to the right within the same row
                for right_idx in range(col_idx + 1, len(row)):
                    right_value = row.iloc[right_idx]
                    if pd.isna(right_value):
                        continue
                    right_text = str(right_value).strip()
                    if right_text:
                        return _normalize_text(right_text)

                # Fallback to checking the cells directly below the label (same column)
                for below_idx in range(row_idx + 1, max_scan_rows):
                    below_value = df.iat[below_idx, col_idx]
                    if pd.isna(below_value):
                        continue
                    below_text = str(below_value).strip()
                    if below_text:
                        return _normalize_text(below_text)

            # Track other non-label values near the top as a final fallback
            if row_idx <= 2 and "name of client" not in lowered:
                fallback = normalized

    if fallback:
        return fallback

    raise ExcelParsingError("Unable to determine client name from spreadsheet header")


def _coerce_tax_year(value: object) -> Optional[str]:
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        year_int = int(value)
        year_str = f"{year_int:04d}"
    else:
        year_str = _normalize_text(str(value))

    if TAX_YEAR_PATTERN.match(year_str):
        return year_str

    # Attempt to coerce string like "2024.0"
    try:
        year_int = int(float(year_str))
    except ValueError:
        return None

    year_str = f"{year_int:04d}"
    if TAX_YEAR_PATTERN.match(year_str):
        return year_str
    return None


def _extract_tax_year(df: pd.DataFrame) -> str:
    """Locate the reported tax year near the top of the worksheet."""

    max_scan_rows = min(10, len(df))

    # Direct check for the expected layout (label in A2, value in B2)
    if max_scan_rows > 1 and df.shape[1] > 1:
        label_candidate = str(df.iat[1, 0]).strip().lower()
        if "tax" in label_candidate and "year" in label_candidate:
            if (year := _coerce_tax_year(df.iat[1, 1])):
                return year

    for row_idx in range(max_scan_rows):
        row = df.iloc[row_idx]
        for col_idx, raw in enumerate(row):
            if pd.isna(raw):
                continue
            text = str(raw).strip()
            if not text:
                continue
            normalized = _normalize_text(text)
            lowered = normalized.lower()
            if "tax" in lowered and "year" in lowered:
                for right_idx in range(col_idx + 1, len(row)):
                    if (year := _coerce_tax_year(row.iloc[right_idx])):
                        return year
                for below_idx in range(row_idx + 1, max_scan_rows):
                    if (year := _coerce_tax_year(df.iat[below_idx, col_idx])):
                        return year

    raise ExcelParsingError(
        "Unable to determine tax year (expecting label 'Tax year' with a YYYY value)."
    )


def _collect_items(df: pd.DataFrame, start_row: int = 3, min_non_empty: int = 1) -> List[str]:
    data_section = df.iloc[start_row:]
    if data_section.empty:
        raise ExcelParsingError("Worksheet does not contain any item rows")

    best_col_idx: Optional[int] = None
    best_count = 0

    for col_idx in range(data_section.shape[1]):
        column = data_section.iloc[:, col_idx]
        count = sum(
            1
            for value in column
            if pd.notna(value)
            and (text := _normalize_text(str(value)))
            and text.lower() != "paste here"
        )
        if count > best_count:
            best_col_idx = col_idx
            best_count = count

    if best_col_idx is None or best_count < min_non_empty:
        raise ExcelParsingError("Unable to find any tax item entries in the spreadsheet")

    col = data_section.iloc[:, best_col_idx]
    items: List[str] = []
    consecutive_empty = 0
    max_empty_gap = 3

    for raw in col:
        text = _normalize_text(str(raw)) if pd.notna(raw) else ""
        if not text or text.lower() == "paste here":
            consecutive_empty += 1
            if consecutive_empty >= max_empty_gap and items:
                break
            continue

        consecutive_empty = 0
        items.append(text)

    if len(items) < min_non_empty:
        raise ExcelParsingError("No worksheet items detected in the spreadsheet")

    return items


def get_client_name_and_items(path: str | Path) -> Tuple[str, str, List[str]]:
    """Parse provided Excel file and return client name, tax year, and worksheet items."""

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    try:
        df = pd.read_excel(path, header=None)
    except Exception as exc:  # pragma: no cover - propagate parsing errors
        raise ExcelParsingError("Failed to read Excel file") from exc

    if df.empty:
        raise ExcelParsingError("Excel file is empty")

    client_name = _find_client_name(df)
    tax_year = _extract_tax_year(df)
    items = _collect_items(df)
    return client_name, tax_year, items


__all__ = [
    "get_client_name_and_items",
    "ExcelParsingError",
]
