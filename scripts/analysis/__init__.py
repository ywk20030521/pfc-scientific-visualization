"""Data-supported PFC analysis and chart selection."""

from .channels import CHANNEL_REGISTRY, channel_definition, classify_history
from .engine import analyze_experiment, load_standardized_case
from .formatting import format_display_series, format_number, formatting_spec
from .intelligence import select_chart_decisions
from .selector import select_charts
from .units import conversion_factor, convert_values, unit_definition

__all__ = [
    "CHANNEL_REGISTRY",
    "channel_definition",
    "classify_history",
    "analyze_experiment",
    "load_standardized_case",
    "format_display_series",
    "format_number",
    "formatting_spec",
    "select_chart_decisions",
    "select_charts",
    "conversion_factor",
    "convert_values",
    "unit_definition",
]

from .physics import (  # noqa: F401
    infer_physics_context, redundancy_analysis, coverage_analysis,
)
