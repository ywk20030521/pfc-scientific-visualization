"""Raw, analysis and display data layer records.

The records are intentionally small interchange objects. They describe lineage
and artifacts; the experiment arrays remain the source of numerical values.
"""
from __future__ import annotations

from typing import Any, Iterable

from .result import RESULT_STATUSES, make_provenance, utc_now

LAYERS = ("ANALYSIS_DATA", "DISPLAY_DATA")


def _artifacts(entries: Iterable[dict[str, Any] | str]) -> list[dict[str, Any]]:
    result = []
    for entry in entries:
        item = {"path": str(entry)} if isinstance(entry, str) else dict(entry)
        if not item.get("path"):
            raise ValueError("A data-layer artifact requires a path")
        item.setdefault("sha256", None)
        item.setdefault("size_bytes", None)
        result.append(item)
    return result


def _layer(
    layer: str,
    case_id: int,
    *,
    artifacts: Iterable[dict[str, Any] | str],
    status: str = "GENERATED",
    provenance: dict[str, Any] | None = None,
    parent_layers: Iterable[str] = (),
    operations: Iterable[dict[str, Any]] = (),
    display: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if layer not in LAYERS:
        raise ValueError(f"Unknown data layer: {layer}")
    if status not in RESULT_STATUSES:
        raise ValueError(f"Unknown data-layer status: {status}")
    return {
        "layer": layer,
        "layer_id": f"{layer.lower()}:case_{int(case_id)}",
        "case_id": int(case_id),
        "status": status,
        "parent_layers": sorted(set(str(parent) for parent in parent_layers)),
        "artifacts": _artifacts(artifacts),
        "operations": [dict(operation) for operation in operations],
        "display": display,
        "provenance": provenance or make_provenance(source="CONFIG"),
        "generated_utc": utc_now(),
    }


def make_analysis_data_layer(
    case_id: int,
    artifacts: Iterable[dict[str, Any] | str],
    *,
    parent_layer_id: str | None = None,
    raw_layer_id: str | None = None,
    operations: Iterable[dict[str, Any]],
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_layer = parent_layer_id or raw_layer_id
    if not source_layer:
        raise ValueError("Analysis data requires a parent source layer")
    operations = list(operations)
    for operation in operations:
        if not operation.get("method") or not operation.get("outputs"):
            raise ValueError("Every analysis operation needs method and outputs")
    return _layer(
        "ANALYSIS_DATA",
        case_id,
        artifacts=artifacts,
        parent_layers=[source_layer],
        operations=operations,
        provenance=provenance,
    )


def make_display_data_layer(
    case_id: int,
    artifacts: Iterable[dict[str, Any] | str],
    *,
    parent_layer_ids: Iterable[str],
    formatting: dict[str, Any],
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not formatting.get("method"):
        raise ValueError("Display data must declare a formatting method")
    return _layer(
        "DISPLAY_DATA",
        case_id,
        artifacts=artifacts,
        parent_layers=parent_layer_ids,
        operations=[
            {
                "method": formatting["method"],
                "inputs": "analysis values by immutable array reference",
                "outputs": "display strings and axis/tooltip formatting metadata",
                "note": "Display values are never used as analysis inputs.",
            }
        ],
        display=dict(formatting),
        provenance=provenance,
    )
