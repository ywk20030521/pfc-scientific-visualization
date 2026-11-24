"""Compatibility entry point for the Chart Intelligence Engine."""
from __future__ import annotations

from typing import Any

from .intelligence import COLOR, select_chart_decisions


def select_charts(
    cases: list[dict[str, Any]],
    comparison: dict[str, Any],
    *,
    overrides: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return selected chart specifications while preserving the legacy API."""
    return select_chart_decisions(cases, comparison, overrides=overrides)["charts"]
