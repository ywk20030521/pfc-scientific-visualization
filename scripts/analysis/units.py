"""Explicit unit metadata and reversible numerical conversions."""
from __future__ import annotations

from typing import Any, Iterable

UNIT_DEFINITIONS: dict[str, dict[str, Any]] = {
    "m": {"quantity": "length", "si_factor": 1.0},
    "mm": {"quantity": "length", "si_factor": 1.0e-3},
    "um": {"quantity": "length", "si_factor": 1.0e-6},
    "km": {"quantity": "length", "si_factor": 1.0e3},
    "s": {"quantity": "time", "si_factor": 1.0},
    "ms": {"quantity": "time", "si_factor": 1.0e-3},
    "N": {"quantity": "force", "si_factor": 1.0},
    "kN": {"quantity": "force", "si_factor": 1.0e3},
    "MN": {"quantity": "force", "si_factor": 1.0e6},
    "N/m": {"quantity": "line_load", "si_factor": 1.0},
    "kN/m": {"quantity": "line_load", "si_factor": 1.0e3},
    "Pa": {"quantity": "stress", "si_factor": 1.0},
    "kPa": {"quantity": "stress", "si_factor": 1.0e3},
    "MPa": {"quantity": "stress", "si_factor": 1.0e6},
    "GPa": {"quantity": "stress", "si_factor": 1.0e9},
    "m/s": {"quantity": "speed", "si_factor": 1.0},
    "m/s^2": {"quantity": "acceleration", "si_factor": 1.0},
    "degree": {"quantity": "angle", "si_factor": 1.0},
    "cycle": {"quantity": "cycle", "si_factor": 1.0},
    "event": {"quantity": "event_count", "si_factor": 1.0},
    "count": {"quantity": "count", "si_factor": 1.0},
    "1": {"quantity": "dimensionless", "si_factor": 1.0},
}


def unit_definition(unit: str) -> dict[str, Any]:
    if unit not in UNIT_DEFINITIONS:
        raise ValueError(f"Unknown unit: {unit}")
    return {"unit": unit, **UNIT_DEFINITIONS[unit]}


def conversion_factor(source_unit: str, target_unit: str) -> float:
    source = unit_definition(source_unit)
    target = unit_definition(target_unit)
    if source["quantity"] != target["quantity"]:
        raise ValueError(
            f"Incompatible units: {source_unit} ({source['quantity']}) and "
            f"{target_unit} ({target['quantity']})"
        )
    return float(source["si_factor"]) / float(target["si_factor"])


def convert_values(
    values: Iterable[float | None],
    source_unit: str,
    target_unit: str,
) -> tuple[list[float | None], dict[str, Any]]:
    """Convert values without mutating the input sequence."""
    factor = conversion_factor(source_unit, target_unit)
    converted = [
        None if value is None else float(value) * factor
        for value in values
    ]
    return converted, {
        "operation": "UNIT_CONVERSION",
        "source_unit": source_unit,
        "target_unit": target_unit,
        "factor": factor,
        "formula": f"x[{target_unit}] = x[{source_unit}] * {factor:.12g}",
        "preserves_missing_values": True,
    }
