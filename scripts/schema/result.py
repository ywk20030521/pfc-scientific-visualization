"""Analysis-result provenance primitives.

The experiment, Case, Channel and Frame schema is owned by pfc-headless and is
embedded in the delivered standardized contract. This module only contains the
small subset needed by analysis and display layer records.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable


RESULT_STATUSES = {
    "GENERATED",
    "NOT_GENERATED",
    "NOT_CAPTURED",
    "NOT_SUPPORTED",
    "INVALID",
    "NOT_VERIFIED",
}
CHANNEL_SOURCES = {
    "REAL_PFC",
    "DERIVED",
    "CONFIG",
    "NOT_CAPTURED",
    "INVALID",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _source(value: str) -> str:
    if value not in CHANNEL_SOURCES:
        raise ValueError(f"Unknown data source: {value}")
    return value


def make_provenance(
    *,
    source: str,
    input_files: Iterable[dict[str, Any] | str] = (),
    parent_results: Iterable[str] = (),
    formula: str | None = None,
    method: str | None = None,
    applicability: str | None = None,
    notes: Iterable[str] = (),
) -> dict[str, Any]:
    files = []
    for entry in input_files:
        item = {"path": str(entry)} if isinstance(entry, str) else dict(entry)
        if "path" not in item:
            raise ValueError("Provenance file entry requires a path")
        item.setdefault("sha256", None)
        item.setdefault("size_bytes", None)
        files.append(item)
    return {
        "source": _source(source),
        "input_files": files,
        "parent_results": sorted(set(str(value) for value in parent_results)),
        "formula": formula,
        "method": method,
        "applicability": applicability,
        "notes": list(notes),
        "generated_utc": utc_now(),
    }
