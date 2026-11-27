"""Canonical dataset layer vocabulary shared across PFC Skills.

Visualization local layers (ANALYSIS_DATA/DISPLAY_DATA) map to the canonical
DERIVED layer. RAW and STANDARDIZED are produced upstream by pfc-headless and
are referenced here by stable ID only, never rewritten.
"""
from __future__ import annotations

from typing import Dict

CANONICAL_LAYERS = ("RAW", "STANDARDIZED", "DERIVED")

LEGACY_TO_CANONICAL: Dict[str, str] = {
    "RAW": "RAW",
    "RAW_DATA": "RAW",
    "STANDARDIZED_DATA": "STANDARDIZED",
    "STANDARDIZED": "STANDARDIZED",
    "ANALYSIS_DATA": "DERIVED",
    "DERIVED": "DERIVED",
    "DERIVED_DATA": "DERIVED",
    "DISPLAY_DATA": "DERIVED",
}

LAYER_OWNER = {
    "RAW": "pfc-headless",
    "STANDARDIZED": "pfc-headless",
    "DERIVED": "pfc-scientific-visualization",
}


def normalize_layer(value: str) -> str:
    key = str(value or "").strip().upper()
    if key not in LEGACY_TO_CANONICAL:
        raise ValueError(f"Unknown dataset layer: {value!r}")
    return LEGACY_TO_CANONICAL[key]


def can_write(skill: str, layer: str) -> bool:
    return LAYER_OWNER.get(normalize_layer(layer)) == skill


__all__ = [
    "CANONICAL_LAYERS", "LEGACY_TO_CANONICAL", "LAYER_OWNER",
    "normalize_layer", "can_write",
]
