"""Explainable, data-driven chart selection.

The engine separates data validity, physical meaning, candidate generation and
presentation scoring. It never creates a chart merely to fill a requested slot.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable

from .formatting import format_display_series
from .units import convert_values

COLOR = {
    "primary": "#3C5488",
    "fracture": "#E64B35",
    "slate": "#8491B4",
    "tan": "#B09C85",
    "accent": "#F39B7F",
    "low": "#EAEEF5",
    "high": "#3C5488",
}

_CHART_REGISTRY_PATH = (
    Path(__file__).resolve().parents[2] / "assets" / "styles" / "chart-type-registry.json"
)
CHART_TYPES = json.loads(_CHART_REGISTRY_PATH.read_text(encoding="utf-8"))

CHANNEL_FEATURES = {
    "mechanical_time_total": {"label": "机械时间", "unit": "s", "role": "time"},
    "cycle": {"label": "Cycle", "unit": "cycle", "role": "cycle"},
    "ball_count": {"label": "颗粒数", "unit": "count", "role": "count"},
    "frame_displacement_mean_m": {
        "label": "平均累计位移",
        "unit": "m",
        "role": "temporal_magnitude",
    },
    "frame_speed_mean_m_s": {
        "label": "平均速度",
        "unit": "m/s",
        "role": "temporal_magnitude",
    },
    "frame_acceleration_mean_m_s2": {
        "label": "平均加速度",
        "unit": "m/s^2",
        "role": "temporal_magnitude",
    },
    "crack_count_cumulative": {
        "label": "累计裂纹",
        "unit": "event",
        "role": "temporal_count",
    },
    "axial_strain": {
        "label": "轴向应变",
        "unit": "1",
        "role": "mechanical_response",
    },
    "axial_stress_pa": {
        "label": "名义轴向应力",
        "unit": "Pa",
        "role": "mechanical_response",
    },
    "axial_load_per_unit_thickness_n_m": {
        "label": "轴向线载荷",
        "unit": "N/m",
        "role": "mechanical_response",
    },
}


def _finite(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _series(case: dict[str, Any], key: str) -> list[Any]:
    return list(case.get("series", {}).get(key, []))


def _finite_pairs(
    x: Iterable[Any], y: Iterable[Any]
) -> tuple[list[float], list[float], list[int], int]:
    left: list[float] = []
    right: list[float] = []
    source_indices: list[int] = []
    missing = 0
    for source_index, (x_value, y_value) in enumerate(zip(x, y)):
        x_number = _finite(x_value)
        y_number = _finite(y_value)
        if x_number is None or y_number is None:
            missing += 1
            continue
        left.append(x_number)
        right.append(y_number)
        source_indices.append(source_index)
    return left, right, source_indices, missing


def channel_features(values: Iterable[Any]) -> dict[str, Any]:
    source = list(values)
    finite = [number for value in source if (number := _finite(value)) is not None]
    if not source:
        return {"status": "NOT_CAPTURED", "count": 0, "missing_count": 0}
    if not finite:
        return {
            "status": "INVALID",
            "count": 0,
            "missing_count": len(source),
        }
    unique_count = len(set(finite))
    return {
        "status": "GENERATED",
        "count": len(finite),
        "missing_count": len(source) - len(finite),
        "min": min(finite),
        "max": max(finite),
        "unique_count": unique_count,
        "constant": unique_count == 1,
        "has_temporal_order": len(finite) >= 3,
    }


def _has_variation(values: Iterable[Any]) -> bool:
    finite = [number for value in values if (number := _finite(value)) is not None]
    if len(finite) < 2:
        return False
    scale = max(abs(min(finite)), abs(max(finite)), 1.0)
    return max(finite) - min(finite) > scale * 1.0e-12


def _decision(
    chart: dict[str, Any],
    *,
    score: float,
    reason: str,
    alternatives: Iterable[dict[str, Any]],
    source_channels: Iterable[str],
    analysis_goal: str,
    derived: bool,
    missing_count: int = 0,
    availability: dict[str, Any] | None = None,
    compatible_types: Iterable[str] = (),
) -> dict[str, Any]:
    result = dict(chart)
    result["source_channels"] = list(source_channels)
    result["analysis_goal"] = analysis_goal
    result["decision"] = {
        "status": "GENERATED",
        "score": round(float(score), 4),
        "reason": reason,
        "alternatives": list(alternatives),
        "derived": bool(derived),
        "missing_count": int(missing_count),
        "manual_override": None,
        "compatible_types": list(compatible_types),
    }
    if availability is not None:
        result["decision"]["availability"] = availability
    return result


def _display(values: Iterable[Any], unit: str) -> dict[str, Any]:
    display = format_display_series(values, unit=unit)
    return {
        "status": display["status"],
        "unit": display["unit"],
        "formatting": display["formatting"],
        "value_materialization": "GENERATED_ON_RENDER",
        "rule": "Per-point display strings are derived from chart values at render time.",
    }


def _with_xy_display(chart: dict[str, Any]) -> dict[str, Any]:
    chart["display"] = {
        "x": _display(chart["x"]["data"], chart["x"]["unit"]),
        "y": _display(chart["y"]["data"], chart["y"]["unit"]),
    }
    return chart


def _with_series_display(chart: dict[str, Any]) -> dict[str, Any]:
    chart["display"] = {
        "x": _display(chart["x"]["data"], chart["x"]["unit"]),
        "series": [
            _display(item["data"], item["unit"])
            for item in chart.get("series", [])
        ],
    }
    return chart


def _axis_contract(
    values: Iterable[Any],
    *,
    zero_required: bool,
    display: dict[str, Any] | None = None,
) -> dict[str, Any]:
    finite = [
        number
        for value in values
        if (number := _finite(value)) is not None
    ]
    observed_min = min(finite) if finite else None
    observed_max = max(finite) if finite else None
    include_zero = bool(
        zero_required
        or (
            observed_min is not None
            and observed_max is not None
            and observed_min <= 0 <= observed_max
        )
    )
    formatting = (display or {}).get("formatting") or {}
    return {
        "range_policy": (
            "ZERO_INCLUDED" if include_zero else "DATA_EXTENT_PADDED"
        ),
        "include_zero": include_zero,
        "observed_min": observed_min,
        "observed_max": observed_max,
        "notation": formatting.get("axis_notation", "DECIMAL"),
        "axis_exponent": formatting.get("axis_exponent"),
        "axis_scale": formatting.get("axis_scale", 1.0),
        "axis_scale_label": formatting.get("axis_scale_label"),
        "decimals": formatting.get("decimals"),
    }


def _with_axis_contract(chart: dict[str, Any]) -> dict[str, Any]:
    chart_type = str(chart.get("type", ""))
    zero_y = chart_type in {
        "area",
        "bar",
        "grouped-bar",
        "stacked-bar",
        "histogram",
    }
    display = chart.get("display") or {}
    if isinstance(chart.get("x"), dict) and isinstance(chart.get("y"), dict):
        chart["axis_contract"] = {
            "x": _axis_contract(
                chart["x"].get("data", []),
                zero_required=False,
                display=display.get("x"),
            ),
            "y": _axis_contract(
                chart["y"].get("data", []),
                zero_required=zero_y,
                display=display.get("y"),
            ),
        }
    elif isinstance(chart.get("x"), dict) and chart.get("series"):
        chart["axis_contract"] = {
            "x": _axis_contract(
                chart["x"].get("data", []),
                zero_required=False,
                display=display.get("x"),
            ),
            "series": [
                _axis_contract(
                    series.get("data", []),
                    zero_required=False,
                    display=(display.get("series") or [])[index]
                    if index < len(display.get("series") or [])
                    else None,
                )
                for index, series in enumerate(chart["series"])
            ],
        }
    elif chart_type == "histogram":
        chart["axis_contract"] = {
            "x": _axis_contract(
                chart.get("edges", []),
                zero_required=False,
                display=display.get("x"),
            ),
            "y": _axis_contract(
                chart.get("counts", []),
                zero_required=True,
                display=display.get("y"),
            ),
        }
    elif chart_type == "case-compare":
        chart["axis_contract"] = {
            "y": _axis_contract(
                [
                    None
                    if _finite(row.get(chart.get("metric_key"))) is None
                    else float(row[chart["metric_key"]]) * float(chart.get("scale", 1))
                    for row in chart.get("data", [])
                ],
                zero_required=True,
                display=display.get("values"),
            )
        }
    return chart


def _candidate_stress_strain(case: dict[str, Any], case_id: int) -> dict[str, Any] | None:
    strain, stress, source_indices, missing = _finite_pairs(
        _series(case, "axial_strain"), _series(case, "axial_stress_pa")
    )
    if len(strain) < 2 or len(stress) < 2:
        return None
    if not _has_variation(strain) or not _has_variation(stress):
        return None
    stress_mpa, conversion = convert_values(stress, "Pa", "MPa")
    chart = {
        "id": f"case_{case_id}:stress_strain",
        "case_id": case_id,
        "type": "line",
        "title": "轴向应力–应变",
        "basis": "Both stress and strain are derived from captured Wall force and platen geometry.",
        "x": {"name": "ε", "unit": "1", "data": strain},
        "y": {"name": "σ", "unit": "MPa", "data": stress_mpa},
        "source_indices": source_indices,
        "color": COLOR["primary"],
        "conversions": [conversion],
    }
    return _decision(
        chart,
        score=0.98,
        reason="Two aligned continuous mechanical-response channels form a monotonic path suitable for a stress–strain curve.",
        alternatives=[
            {"type": "scatter", "score": 0.82, "reason": "Possible, but the path order carries deformation history."},
            {"type": "histogram", "score": 0.35, "reason": "Would discard the pairwise relationship."},
        ],
        source_channels=["sample.axial_strain", "sample.axial_stress"],
        analysis_goal="mechanical_response_path",
        derived=True,
        missing_count=missing,
        compatible_types=["line", "scatter"],
    )


def _candidate_line_load_strain(case: dict[str, Any], case_id: int) -> dict[str, Any] | None:
    strain, load, source_indices, missing = _finite_pairs(
        _series(case, "axial_strain"),
        _series(case, "axial_load_per_unit_thickness_n_m"),
    )
    if len(strain) < 2 or len(load) < 2:
        return None
    if not _has_variation(strain) or not _has_variation(load):
        return None
    load_kn_m, conversion = convert_values(load, "N/m", "kN/m")
    chart = {
        "id": f"case_{case_id}:line_load_strain",
        "case_id": case_id,
        "type": "line",
        "title": "PFC2D 轴向线载荷–应变",
        "basis": "PFC2D force per unit out-of-plane thickness from captured Wall force and geometry.",
        "x": {"name": "ε", "unit": "1", "data": strain},
        "y": {"name": "q", "unit": "kN/m", "data": load_kn_m},
        "source_indices": source_indices,
        "color": COLOR["primary"],
        "conversions": [conversion],
    }
    return _decision(
        chart,
        score=0.97,
        reason="PFC2D native force basis is line load in N/m; plotting it as Pa stress would be dimensionally misleading.",
        alternatives=[
            {"type": "scatter", "score": 0.80, "reason": "Useful for sparse samples; line is preferred for ordered loading."},
        ],
        source_channels=["sample.axial_strain", "sample.axial_load_per_unit_thickness"],
        analysis_goal="pfc2d_mechanical_response_path",
        derived=True,
        missing_count=missing,
        compatible_types=["line", "scatter"],
    )


def _candidate_time_response(
    case: dict[str, Any],
    case_id: int,
    *,
    y_key: str,
    y_name: str,
    y_unit: str,
    scale: float,
    title: str,
    reason: str,
    color: str,
    source_channel: str,
    chart_name: str,
) -> dict[str, Any] | None:
    times = _series(case, "mechanical_time_total")
    values = _series(case, y_key)
    source_count = min(len(times), len(values))
    times = times[:source_count]
    values = values[:source_count]
    finite_values = [
        number for value in values if (number := _finite(value)) is not None
    ]
    missing = len(values) - len(finite_values)
    if len(finite_values) < 3:
        return None
    if not _has_variation(times) or not _has_variation(finite_values):
        return None
    scaled_values = [
        None if (number := _finite(value)) is None else number / scale
        for value in values
    ]
    chart = {
        "id": f"case_{case_id}:{chart_name}",
        "case_id": case_id,
        "type": "line",
        "title": title,
        "basis": reason,
        "x": {"name": "机械时间", "unit": "s", "data": times},
        "y": {"name": y_name, "unit": y_unit, "data": scaled_values},
        "source_indices": list(range(source_count)),
        "color": color,
    }
    return _decision(
        chart,
        score=0.91,
        reason="At least three finite frame-aligned mechanical-time samples preserve the temporal trend without interpolation.",
        alternatives=[
            {"type": "area", "score": 0.73, "reason": "Adds magnitude emphasis without improving trend identification."},
            {"type": "scatter", "score": 0.60, "reason": "Shows real observations but obscures continuity."},
        ],
        source_channels=["mechanical_time_total", source_channel],
        analysis_goal="temporal_trend",
        derived=True,
        missing_count=missing,
        compatible_types=["line", "area", "scatter"],
    )


def _candidate_motion_cracks(case: dict[str, Any], case_id: int) -> dict[str, Any] | None:
    cycle = _series(case, "cycle")
    motion = _series(case, "frame_displacement_mean_m")
    cracks = _series(case, "crack_count_cumulative")
    source_count = min(len(cycle), len(motion), len(cracks))
    if not case.get("crack_available") or source_count < 2:
        return None
    cycle = cycle[:source_count]
    motion = motion[:source_count]
    cracks = cracks[:source_count]
    if not _has_variation(cycle) or not _has_variation(motion):
        return None
    chart = {
        "id": f"case_{case_id}:motion_cracks",
        "case_id": case_id,
        "type": "dual-line",
        "title": "颗粒运动与裂纹演化",
        "basis": "Both series use captured frames; no synthetic intermediate states.",
        "x": {"name": "Cycle", "unit": "cycle", "data": cycle},
        "source_indices": list(range(source_count)),
        "series": [
            {
                "name": "平均位移",
                "unit": "m",
                "axis": 0,
                "color": COLOR["slate"],
                "data": motion,
            },
            {
                "name": "累计裂纹",
                "unit": "event",
                "axis": 1,
                "color": COLOR["fracture"],
                "data": cracks,
                "source": "DERIVED",
            },
        ],
    }
    return _decision(
        chart,
        score=0.95,
        reason="Motion and cumulative captured fracture events share real Cycle indices, so a two-axis temporal view shows their co-evolution.",
        alternatives=[
            {"type": "line", "score": 0.68, "reason": "Separate scales would make event counts and displacement difficult to compare."},
        ],
        source_channels=["ball.displacement", "fracture.cumulative", "cycle"],
        analysis_goal="temporal_coevolution",
        derived=True,
        compatible_types=["dual-line"],
    )


def _candidate_motion(case: dict[str, Any], case_id: int) -> dict[str, Any] | None:
    cycle = _series(case, "cycle")
    motion = _series(case, "frame_displacement_mean_m")
    source_count = min(len(cycle), len(motion))
    if source_count < 2:
        return None
    cycle = cycle[:source_count]
    motion = motion[:source_count]
    if not _has_variation(cycle) or not _has_variation(motion):
        return None
    chart = {
        "id": f"case_{case_id}:motion",
        "case_id": case_id,
        "type": "area",
        "title": "颗粒平均位移",
        "basis": "Mean displacement over present captured Ball IDs at each real frame.",
        "x": {"name": "Cycle", "unit": "cycle", "data": cycle},
        "y": {"name": "平均位移", "unit": "m", "data": motion},
        "source_indices": list(range(source_count)),
        "color": COLOR["slate"],
    }
    return _decision(
        chart,
        score=0.80,
        reason="The channel is an ordered frame summary and is useful even when fracture data is absent.",
        alternatives=[
            {"type": "area", "score": 0.64, "reason": "A filled trend is decorative when the baseline is not zero."},
        ],
        source_channels=["ball.displacement", "cycle"],
        analysis_goal="temporal_trend",
        derived=True,
        compatible_types=["line", "area"],
    )


def _candidate_histogram(case: dict[str, Any], case_id: int) -> dict[str, Any] | None:
    histogram = case.get("histograms", {}).get("final_displacement_m", {})
    counts = histogram.get("counts", [])
    edges = histogram.get("edges", [])
    labels = histogram.get("labels", [])
    if histogram.get("status") != "GENERATED" or len(counts) < 1 or len(edges) < 2:
        return None
    chart = {
        "id": f"case_{case_id}:displacement_hist",
        "case_id": case_id,
        "type": "histogram",
        "title": "末帧颗粒累计位移分布",
        "basis": "Distribution of real final-frame particle displacements.",
        "counts": counts,
        "edges": edges,
        "bins": histogram.get("bins", []),
        "bin_labels": labels,
        "range_policy": histogram.get(
            "range_policy", "ROBUST_P05_P95_WITH_OVERFLOW"
        ),
        "total_count": histogram.get("total_count"),
        "finite_count": histogram.get("finite_count"),
        "missing_count": histogram.get("missing_count"),
        "underflow_count": histogram.get("underflow_count"),
        "overflow_count": histogram.get("overflow_count"),
        "interior_quantiles": histogram.get("interior_quantiles"),
        "interior_min": histogram.get("interior_min"),
        "interior_max": histogram.get("interior_max"),
        "observed_min": histogram.get("observed_min"),
        "observed_max": histogram.get("observed_max"),
        "color": COLOR["slate"],
    }
    chart["display"] = {
        "x": _display(
            [
                value if _finite(value) is not None else None
                for value in labels
            ],
            "m",
        ),
        "y": _display(counts, "count"),
    }
    return _decision(
        chart,
        score=0.90,
        reason=(
            "The final real frame provides a finite particle distribution. "
            "The P05-P95 interior is displayed continuously while all lower and "
            "upper tail observations remain in explicit overflow bins."
        ),
        alternatives=[
            {"type": "boxplot", "score": 0.74, "reason": "Compact for summary comparison but hides multimodality."},
        ],
        source_channels=["ball.displacement"],
        analysis_goal="spatial_distribution",
        derived=True,
        missing_count=int(histogram.get("missing_count", 0)),
        compatible_types=["histogram", "boxplot"],
    )


def _candidate_rose(case: dict[str, Any], case_id: int) -> dict[str, Any] | None:
    orientation = case.get("orientation", {})
    angles = orientation.get("azimuth_deg", [])
    if orientation.get("status") != "GENERATED" or not angles:
        return None
    chart = {
        "id": f"case_{case_id}:fracture_rose",
        "case_id": case_id,
        "type": "rose",
        "title": "裂纹方向分布",
        "basis": "Rose angles come from captured fracture normals.",
        "angles": angles,
        "color": COLOR["fracture"],
    }
    chart["display"] = {"angles": _display(angles, "degree")}
    return _decision(
        chart,
        score=0.89,
        reason="Captured fracture normals provide circular directional observations; a polar frequency view preserves angular meaning.",
        alternatives=[
            {"type": "polar", "score": 0.77, "reason": "Equivalent coordinate system with less direct bin comparison."},
            {"type": "histogram", "score": 0.42, "reason": "Linear bins break the 0/360-degree continuity."},
        ],
        source_channels=["fracture.orientation"],
        analysis_goal="direction_distribution",
        derived=True,
        compatible_types=["rose", "polar"],
    )


def _candidate_density(case: dict[str, Any], case_id: int) -> dict[str, Any] | None:
    density = case.get("spatial_density", {})
    if (
        density.get("status") != "GENERATED"
        or not density.get("x_edges")
        or not density.get("y_edges")
        or not density.get("counts")
    ):
        return None
    dimension = int(case.get("dimension", 3))
    projection = " XY 投影" if dimension == 3 else ""
    chart = {
        "id": f"case_{case_id}:particle_density",
        "case_id": case_id,
        "type": "heatmap",
        "title": f"末帧{projection}颗粒数密度",
        "basis": (
            "Particle-count density from the final captured frame"
            + (" projected onto XY; not a 3D physical field." if dimension == 3 else ", not a stress or strain field.")
        ),
        "x": density["x_edges"],
        "y": density["y_edges"],
        "z": density["counts"],
        "color": [COLOR["low"], COLOR["high"]],
    }
    chart["display"] = {
        "x": _display(density["x_edges"], "m"),
        "y": _display(density["y_edges"], "m"),
        "z": _display(
            [value for row in density["counts"] for value in row],
            "count",
        ),
    }
    return _decision(
        chart,
        score=0.86,
        reason="The final real frame has XY coordinates; binned counts expose spatial heterogeneity without claiming a physical field.",
        alternatives=[
            {"type": "scatter", "score": 0.58, "reason": "Would overplot dense particles and obscure count gradients."},
        ],
        source_channels=["ball.position"],
        analysis_goal="spatial_distribution",
        derived=True,
        compatible_types=["heatmap"],
    )


def _candidate_particle_size(case: dict[str, Any], case_id: int) -> dict[str, Any] | None:
    histogram = case.get("histograms", {}).get("particle_radius_m", {})
    counts = histogram.get("counts", [])
    edges = histogram.get("edges", [])
    labels = histogram.get("labels", [])
    if histogram.get("status") != "GENERATED" or len(counts) < 1 or len(edges) < 2:
        return None
    chart = {
        "id": f"case_{case_id}:particle_size",
        "case_id": case_id,
        "type": "histogram",
        "title": "颗粒尺寸分布",
        "basis": "Distribution of declared per-Ball radius in the final frame (MOCK showcase).",
        "counts": counts,
        "edges": edges,
        "bins": histogram.get("bins", []),
        "bin_labels": labels,
        "range_policy": histogram.get("range_policy", "ROBUST_P05_P95_WITH_OVERFLOW"),
        "total_count": histogram.get("total_count"),
        "finite_count": histogram.get("finite_count"),
        "observed_min": histogram.get("observed_min"),
        "observed_max": histogram.get("observed_max"),
        "value_name": "半径",
        "color": COLOR["slate"],
    }
    chart["display"] = {
        "x": _display([v if _finite(v) is not None else None for v in labels], "m"),
        "y": _display(counts, "count"),
    }
    return _decision(
        chart,
        score=0.88,
        reason="The final frame provides a finite per-Ball radius distribution; a histogram preserves the size spectrum.",
        alternatives=[
            {"type": "boxplot", "score": 0.66, "reason": "Summarizes spread but hides modality."},
        ],
        source_channels=["ball.radius"],
        analysis_goal="distribution",
        derived=False,
        compatible_types=["histogram", "boxplot"],
    )


def _candidate_spatial_strain(case: dict[str, Any], case_id: int) -> dict[str, Any] | None:
    field = case.get("spatial_strain", {})
    if (
        field.get("status") != "GENERATED"
        or not field.get("x_edges") or not field.get("y_edges") or not field.get("values")
    ):
        return None
    chart = {
        "id": f"case_{case_id}:spatial_strain",
        "case_id": case_id,
        "type": "heatmap",
        "title": "末帧空间应变场",
        "basis": field.get("method", "Declared per-Ball strain binned on final-frame XY."),
        "x": field["x_edges"],
        "y": field["y_edges"],
        "z": field["values"],
        "value_name": "局部应变",
        "unit": field.get("unit", "1"),
        "color": [COLOR["low"], COLOR["high"]],
    }
    chart["display"] = {
        "x": _display(field["x_edges"], "m"),
        "y": _display(field["y_edges"], "m"),
        "z": _display(
            [v for row in field["values"] for v in row if v is not None], field.get("unit", "1")
        ),
    }
    return _decision(
        chart,
        score=0.87,
        reason="A declared per-Ball strain field is binned on real final-frame XY coordinates; no density or displacement is reinterpreted as strain.",
        alternatives=[
            {"type": "scatter", "score": 0.52, "reason": "Overplots dense particles."},
        ],
        source_channels=["ball.local_strain"],
        analysis_goal="spatial_distribution",
        derived=True,
        compatible_types=["heatmap"],
    )


def _candidate_particle_orientation(case: dict[str, Any], case_id: int) -> dict[str, Any] | None:
    orient = case.get("ball_orientation", {})
    counts = orient.get("counts", [])
    edges = orient.get("edges_deg", [])
    if orient.get("status") != "GENERATED" or len(counts) < 2 or len(edges) < 3:
        return None
    chart = {
        "id": f"case_{case_id}:particle_orientation",
        "case_id": case_id,
        "type": "rose",
        "title": "颗粒朝向分布",
        "basis": "Declared per-Ball orientation angles binned into 180-degree sectors (MOCK showcase).",
        "sector_counts": counts,
        "sector_edges_deg": edges,
        "percent": orient.get("percent", []),
        "color": COLOR["slate"],
    }
    chart["display"] = {"angles": _display(edges, "degree")}
    return _decision(
        chart,
        score=0.85,
        reason="Declared per-Ball orientation angles preserve circular meaning; a polar frequency view is appropriate.",
        alternatives=[
            {"type": "histogram", "score": 0.44, "reason": "Linear bins break angular continuity."},
        ],
        source_channels=["ball.orientation"],
        analysis_goal="direction_distribution",
        derived=False,
        compatible_types=["rose", "polar"],
    )


def _candidate_correlation(case: dict[str, Any], case_id: int) -> dict[str, Any] | None:
    correlation = case.get("correlation", {})
    if correlation.get("status") != "GENERATED":
        return None
    source_labels = correlation.get("labels", [])
    values = correlation.get("values", [])
    if len(source_labels) < 2 or len(values) != len(source_labels):
        return None
    labels = [
        CHANNEL_FEATURES.get(label, {}).get("label", label)
        for label in source_labels
    ]
    chart = {
        "id": f"case_{case_id}:correlation",
        "case_id": case_id,
        "type": "correlation",
        "title": "通道相关性",
        "basis": correlation["method"],
        "labels": labels,
        "source_labels": source_labels,
        "values": values,
        "color": [COLOR["fracture"], "#FFFFFF", COLOR["primary"]],
    }
    return _decision(
        chart,
        score=0.75,
        reason="At least two frame-aligned finite channels vary; a compact matrix shows pairwise association for exploration.",
        alternatives=[
            {"type": "scatter", "score": 0.66, "reason": "Better for one selected pair but requires multiple panels for all pairs."},
        ],
        source_channels=source_labels,
        analysis_goal="multivariate_association",
        derived=True,
        compatible_types=["correlation"],
    )


def _comparison_metric_contract(
    comparison: dict[str, Any],
    metric_key: str,
    metric_unit: str,
) -> dict[str, Any]:
    cases = list(comparison.get("cases", []))
    contract = (comparison.get("metrics") or {}).get(metric_key)
    finite_case_ids = [
        int(row["case_id"])
        for row in cases
        if _finite(row.get(metric_key)) is not None
    ]
    missing_case_ids = [
        int(row["case_id"])
        for row in cases
        if _finite(row.get(metric_key)) is None
    ]
    if contract is None:
        contract = {
            "status": "GENERATED" if len(finite_case_ids) >= 2 else "NOT_GENERATED",
            "unit": metric_unit,
            "total_case_count": len(cases),
            "available_case_count": len(finite_case_ids),
            "missing_case_count": len(missing_case_ids),
            "missing_case_ids": missing_case_ids,
            "comparable": len(finite_case_ids) >= 2,
            "not_comparable_reason": (
                None
                if len(finite_case_ids) >= 2
                else "Fewer than two Cases provide a finite native/final value."
            ),
            "cases": [
                {
                    "case_id": int(row["case_id"]),
                    "value": _finite(row.get(metric_key)),
                    "state": (
                        "AVAILABLE"
                        if _finite(row.get(metric_key)) is not None
                        else "NOT_CAPTURED"
                    ),
                    "reason": (
                        None
                        if _finite(row.get(metric_key)) is not None
                        else "LEGACY_COMPARISON:NOT_CAPTURED"
                    ),
                }
                for row in cases
            ],
            "availability_source": "DERIVED_FROM_LEGACY_COMPARISON_CASES",
        }
    if (
        int(contract.get("total_case_count", -1)) != len(cases)
        or int(contract.get("available_case_count", -1)) != len(finite_case_ids)
        or int(contract.get("missing_case_count", -1)) != len(missing_case_ids)
        or [int(value) for value in contract.get("missing_case_ids", [])]
        != missing_case_ids
    ):
        raise ValueError(
            f"Comparison availability contract is inconsistent for {metric_key}"
        )
    return contract


def _case_comparison_charts(
    comparison: dict[str, Any],
) -> list[dict[str, Any]]:
    if comparison.get("status") != "GENERATED":
        return []
    charts = []
    metrics = [
        (
            "stress_max_pa",
            "峰值名义应力",
            "MPa",
            1.0e-6,
            "sample.axial_stress",
            COLOR["primary"],
        ),
        (
            "displacement_mean_m",
            "平均位移",
            "m",
            1.0,
            "ball.displacement",
            COLOR["slate"],
        ),
        (
            "crack_final",
            "末帧累计裂纹",
            "event",
            1.0,
            "fracture.cumulative",
            COLOR["fracture"],
        ),
    ]
    for (
        metric_key,
        metric_name,
        metric_unit,
        scale,
        source_channel,
        metric_color,
    ) in metrics:
        availability = _comparison_metric_contract(
            comparison, metric_key, metric_unit
        )
        if not availability.get("comparable"):
            continue
        chart = {
            "id": f"experiment:case_comparison:{metric_key}",
            "case_id": None,
            "type": "case-compare",
            "title": f"多 Case {metric_name}",
            "basis": "Per-case native/final summaries; no time interpolation.",
            "data": comparison["cases"],
            "metric_key": metric_key,
            "metric_name": metric_name,
            "metric_unit": metric_unit,
            "scale": scale,
            "color": metric_color,
            "color_policy": "SINGLE_COLOR_BY_METRIC_SEMANTICS",
            "total_case_count": int(availability["total_case_count"]),
            "available_case_count": int(availability["available_case_count"]),
            "missing_case_count": int(availability["missing_case_count"]),
            "missing_case_ids": list(availability["missing_case_ids"]),
            "case_availability": list(availability.get("cases", [])),
        }
        chart["display"] = {
            "values": _display(
                [
                    None
                    if _finite(row.get(metric_key)) is None
                    else float(row[metric_key]) * scale
                    for row in comparison["cases"]
                ],
                metric_unit,
            )
        }
        _with_axis_contract(chart)
        charts.append(
            _decision(
                chart,
                score=0.88,
                reason="At least two Cases provide the same native/final metric, so a common-semantics comparison is informative.",
                alternatives=[
                    {"type": "boxplot", "score": 0.62, "reason": "Requires within-Case distributions rather than one final summary."},
                ],
                source_channels=[source_channel],
                analysis_goal="multi_case_comparison",
                derived=True,
                missing_count=int(availability["missing_case_count"]),
                availability={
                    "total_case_count": int(availability["total_case_count"]),
                    "available_case_count": int(availability["available_case_count"]),
                    "missing_case_count": int(availability["missing_case_count"]),
                    "missing_case_ids": list(availability["missing_case_ids"]),
                    "not_comparable_reason": availability.get(
                        "not_comparable_reason"
                    ),
                },
                compatible_types=["bar", "case-compare"],
            )
        )
    return charts


def _rejected_conditions(cases: list[dict[str, Any]], comparison: dict[str, Any]) -> list[dict[str, Any]]:
    rejected = []
    seen: set[str] = set()

    def reject(case_id: Any, chart_name: str, status: str, reason: str) -> None:
        chart_id = f"case_{case_id}:{chart_name}"
        if chart_id in seen:
            return
        seen.add(chart_id)
        rejected.append(
            {
                "id": chart_id,
                "case_id": case_id,
                "chart_name": chart_name,
                "status": status,
                "reason": reason,
            }
        )

    for case in cases:
        case_id = case.get("case_id")
        response = _series(case, "axial_stress_pa")
        strain = _series(case, "axial_strain")
        line_load = _series(case, "axial_load_per_unit_thickness_n_m")
        valid_response = any(_finite(value) is not None for value in response)
        valid_strain = any(_finite(value) is not None for value in strain)
        valid_line_load = any(_finite(value) is not None for value in line_load)
        if not valid_response:
            reject(
                case_id,
                "stress_strain",
                "NOT_CAPTURED",
                "No valid stress channel exists; no stress chart was generated.",
            )
            reject(
                case_id,
                "stress_time",
                "NOT_CAPTURED",
                "No valid stress channel exists; no stress–time chart was generated.",
            )
        elif not valid_strain:
            reject(
                case_id,
                "stress_strain",
                "NOT_GENERATED",
                "Stress exists but strain is unavailable, so a stress–strain relationship is not supported.",
            )
        elif not _has_variation(strain) or not _has_variation(response):
            reject(
                case_id,
                "stress_strain",
                "NOT_GENERATED",
                "Stress or strain is constant across all captured frames, so the relationship has no evident statistical information.",
            )
            reject(
                case_id,
                "stress_time",
                "NOT_GENERATED",
                "Stress is constant across all captured frames, so a stress–time trend would be visually flat and non-informative.",
            )
        if valid_line_load and not _has_variation(line_load):
            reject(
                case_id,
                "line_load_time",
                "NOT_GENERATED",
                "PFC2D line load is constant across all captured frames, so a line-load–time trend is omitted.",
            )
        if not case.get("crack_available"):
            reject(
                case_id,
                "motion_cracks",
                "NOT_CAPTURED",
                "No captured fracture events; the motion–crack evolution and fracture-orientation charts are omitted.",
            )
            reject(
                case_id,
                "fracture_rose",
                "NOT_CAPTURED",
                "No captured fracture normals; a direction rose would fabricate orientation data.",
            )
        if not valid_line_load:
            reject(
                case_id,
                "line_load_time",
                "NOT_CAPTURED",
                "No valid PFC2D line-load channel exists; the temporal line-load chart is omitted.",
            )
        if valid_line_load and valid_strain and (
            not _has_variation(line_load) or not _has_variation(strain)
        ):
            reject(
                case_id,
                "line_load_strain",
                "NOT_GENERATED",
                "PFC2D line load or strain is constant, so a mechanical-response path is omitted.",
            )
        elif not valid_strain or not valid_line_load:
            reject(
                case_id,
                "line_load_strain",
                "NOT_CAPTURED",
                "Both valid PFC2D line load and strain are required for the mechanical-response path.",
            )
        speed = [
            value for value in _series(case, "frame_speed_mean_m_s")
            if _finite(value) is not None
        ]
        if len(speed) < 3:
            reject(
                case_id,
                "speed_time",
                "NOT_GENERATED",
                "Fewer than three finite speed samples cannot support a meaningful temporal trend.",
            )
        elif not _has_variation(speed):
            reject(
                case_id,
                "speed_time",
                "NOT_GENERATED",
                "Speed is constant across captured frames, so a temporal trend is omitted.",
            )
        acceleration = [
            value for value in _series(case, "frame_acceleration_mean_m_s2")
            if _finite(value) is not None
        ]
        if acceleration and len(acceleration) < 3:
            reject(
                case_id,
                "acceleration_time",
                "NOT_GENERATED",
                "Fewer than three finite acceleration samples cannot support a meaningful temporal trend.",
            )
        elif acceleration and not _has_variation(acceleration):
            reject(
                case_id,
                "acceleration_time",
                "NOT_GENERATED",
                "Acceleration is constant across captured frames, so a temporal trend is omitted.",
            )
        elif not acceleration:
            reject(
                case_id,
                "acceleration_time",
                "NOT_CAPTURED",
                "No valid particle acceleration history was derived for this Case.",
            )
        motion = _series(case, "frame_displacement_mean_m")
        if not motion:
            reject(
                case_id,
                "motion",
                "NOT_CAPTURED",
                "No finite particle-displacement summary exists for the temporal motion chart.",
            )
        if motion and not _has_variation(motion):
            reject(
                case_id,
                "motion",
                "NOT_GENERATED",
                "Mean displacement is constant across captured frames, so a temporal trend is omitted.",
            )
        histogram = case.get("histograms", {}).get("final_displacement_m", {})
        if histogram.get("status") != "GENERATED":
            reject(
                case_id,
                "displacement_hist",
                str(histogram.get("status") or "NOT_CAPTURED"),
                "A final-frame displacement histogram was not generated because the required finite particle distribution is unavailable.",
            )
        density = case.get("spatial_density", {})
        if density.get("status") != "GENERATED":
            reject(
                case_id,
                "particle_density",
                str(density.get("status") or "NOT_CAPTURED"),
                "A spatial particle-count map was not generated because real final-frame coordinates or supported bins are unavailable.",
            )
        correlation = case.get("correlation", {})
        if correlation.get("status") != "GENERATED":
            reject(
                case_id,
                "correlation",
                str(correlation.get("status") or "NOT_CAPTURED"),
                "A correlation matrix was not generated because fewer than two aligned varying channels are available.",
            )
        orientation = case.get("orientation", {})
        if case.get("crack_available") and orientation.get("status") != "GENERATED":
            reject(
                case_id,
                "fracture_rose",
                str(orientation.get("status") or "INVALID"),
                "Captured fracture events do not provide valid normals suitable for a direction distribution.",
            )
    if comparison.get("status") != "GENERATED":
        rejected.append(
            {
                "id": "experiment:case_comparison",
                "case_id": None,
                "chart_name": "case_comparison",
                "status": "NOT_GENERATED",
                "reason": comparison.get("reason", "A comparison requires at least two Cases."),
            }
        )
    else:
        for metric_key, metric_name in (
            ("stress_max_pa", "peak nominal stress"),
            ("displacement_mean_m", "mean displacement"),
            ("crack_final", "final cumulative fracture count"),
        ):
            availability = _comparison_metric_contract(
                comparison,
                metric_key,
                "UNKNOWN",
            )
            if availability.get("comparable"):
                continue
            rejected.append(
                {
                    "id": f"experiment:case_comparison:{metric_key}",
                    "case_id": None,
                    "chart_name": "case_comparison",
                    "status": "NOT_GENERATED",
                    "reason": (
                        f"The {metric_name} comparison is omitted: "
                        + str(
                            availability.get("not_comparable_reason")
                            or "fewer than two Cases provide the metric."
                        )
                    ),
                }
            )
    return rejected


def _apply_overrides(
    charts: list[dict[str, Any]],
    overrides: dict[str, Any] | None,
) -> None:
    if not overrides:
        return
    mapping = overrides.get("charts", overrides)
    if not isinstance(mapping, dict):
        raise ValueError("Chart overrides must be an object keyed by chart ID")
    by_id = {chart["id"]: chart for chart in charts}
    for chart_id, value in mapping.items():
        chart = by_id.get(chart_id)
        if chart is None:
            continue
        config = {"type": value} if isinstance(value, str) else dict(value)
        requested_type = config.get("type")
        compatible = chart["decision"].get("compatible_types", [])
        if requested_type and requested_type not in compatible:
            chart["decision"]["manual_override"] = {
                "status": "REJECTED",
                "requested_type": requested_type,
                "reason": "The requested type is incompatible with the chart's data structure.",
            }
            continue
        if requested_type:
            chart["type"] = str(requested_type)
        if isinstance(config.get("options"), dict):
            chart["options"] = dict(config["options"])
        chart["decision"]["manual_override"] = {
            "status": "APPLIED",
            "requested_type": requested_type,
        }


def _chart_units(chart: dict[str, Any]) -> Any:
    if isinstance(chart.get("metric_unit"), str):
        return chart["metric_unit"]
    if isinstance(chart.get("y"), dict) and chart["y"].get("unit"):
        return chart["y"]["unit"]
    series_units = [
        item.get("unit")
        for item in chart.get("series", [])
        if item.get("unit")
    ]
    if series_units:
        return series_units[0] if len(set(series_units)) == 1 else series_units
    if chart.get("type") == "correlation":
        return "Pearson r"
    if chart.get("type") == "rose":
        return "degree"
    if chart.get("type") in {"heatmap", "histogram"}:
        return "count"
    return None


def _finite_count_from_chart(chart: dict[str, Any]) -> int:
    if chart.get("type") == "histogram":
        return int(chart.get("finite_count") or sum(chart.get("counts", [])))
    if chart.get("type") == "heatmap":
        return sum(
            int(value)
            for row in chart.get("counts", [])
            for value in row
            if _finite(value) is not None
        )
    if chart.get("type") == "case-compare":
        return int(chart.get("available_case_count", 0))
    values: list[Any] = []
    if isinstance(chart.get("y"), dict):
        values.extend(chart["y"].get("data", []))
    for series in chart.get("series", []):
        values.extend(series.get("data", []))
    if not values and isinstance(chart.get("x"), dict):
        values.extend(chart["x"].get("data", []))
    return sum(1 for value in values if _finite(value) is not None)


def _publication_priority(score: float) -> str:
    if score >= 0.9:
        return "HIGH"
    if score >= 0.75:
        return "MEDIUM"
    return "SUPPORTING"


def _finalize_selected_chart(chart: dict[str, Any]) -> None:
    decision = chart["decision"]
    source_channels = [str(value) for value in chart.get("source_channels", [])]
    chart["chart_id"] = str(chart["id"])
    chart["chart_type"] = str(chart["type"])
    chart["source_variables"] = source_channels
    chart["source_data"] = {
        "channels": source_channels,
        "analysis_goal": chart.get("analysis_goal"),
        "basis": chart.get("basis"),
        "derived": bool(decision.get("derived")),
    }
    chart["physical_meaning"] = chart.get("basis") or decision.get("reason")
    chart["unit"] = _chart_units(chart)
    chart["selection_reason"] = decision.get("reason")
    chart["omission_reason"] = None
    chart["data_quality"] = {
        "status": decision.get("status"),
        "finite_count": _finite_count_from_chart(chart),
        "missing_count": int(decision.get("missing_count", 0)),
        "constant_channel_rejected": False,
        "missing_values_treated_as_zero": False,
    }
    chart["publication_priority"] = _publication_priority(
        float(decision.get("score", 0.0))
    )


_OMISSION_MEANINGS = {
    "stress_strain": ("line", ["sample.axial_strain", "sample.axial_stress"], "MPa"),
    "line_load_strain": (
        "line",
        ["sample.axial_strain", "sample.axial_load_per_unit_thickness"],
        "kN/m",
    ),
    "stress_time": ("line", ["mechanical_time_total", "sample.axial_stress"], "MPa"),
    "line_load_time": (
        "line",
        ["mechanical_time_total", "sample.axial_load_per_unit_thickness"],
        "kN/m",
    ),
    "speed_time": ("line", ["mechanical_time_total", "ball.velocity"], "m/s"),
    "acceleration_time": (
        "line",
        ["mechanical_time_total", "ball.acceleration"],
        "m/s^2",
    ),
    "motion_cracks": (
        "dual-line",
        ["ball.displacement", "fracture.cumulative", "cycle"],
        "m,event",
    ),
    "motion": ("area", ["ball.displacement", "cycle"], "m"),
    "displacement_hist": ("histogram", ["ball.displacement"], "count"),
    "fracture_rose": ("rose", ["fracture.orientation"], "degree"),
    "particle_density": ("heatmap", ["ball.position"], "count"),
    "correlation": ("correlation", ["aligned finite analysis channels"], "Pearson r"),
}


def _finalize_rejected_chart(item: dict[str, Any]) -> None:
    chart_name = str(item.get("chart_name") or item["id"].rsplit(":", 1)[-1])
    chart_type, source_variables, unit = _OMISSION_MEANINGS.get(
        chart_name,
        ("not-generated", [], None),
    )
    item["chart_id"] = str(item["id"])
    item["chart_type"] = str(item.get("chart_type") or chart_type)
    item["source_variables"] = list(
        item.get("source_variables") or source_variables
    )
    item["source_data"] = {
        "channels": list(item["source_variables"]),
        "status": item["status"],
    }
    item["physical_meaning"] = item.get("physical_meaning") or (
        "The candidate is recorded so a scientifically unsupported omission remains traceable."
    )
    item["unit"] = item.get("unit", unit)
    item["selection_reason"] = None
    item["omission_reason"] = str(item["reason"])
    item["data_quality"] = {
        "status": item["status"],
        "missing_values_treated_as_zero": False,
        "constant_channel_rejected": "constant" in item["reason"].lower(),
    }
    item["publication_priority"] = "EXCLUDED"


def select_chart_decisions(
    cases: list[dict[str, Any]],
    comparison: dict[str, Any],
    *,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    charts: list[dict[str, Any]] = []
    for case in cases:
        if case.get("status", "GENERATED") != "GENERATED":
            continue
        case_id = int(case["case_id"])
        candidates = [
            _candidate_stress_strain(case, case_id),
            _candidate_line_load_strain(case, case_id),
            _candidate_time_response(
                case,
                case_id,
                y_key="axial_stress_pa",
                y_name="σ",
                y_unit="MPa",
                scale=1.0e6,
                title="名义应力–机械时间",
                reason="Frame-aligned native mechanical time and derived nominal stress.",
                color=COLOR["primary"],
                source_channel="sample.axial_stress",
                chart_name="stress_time",
            ),
            _candidate_time_response(
                case,
                case_id,
                y_key="axial_load_per_unit_thickness_n_m",
                y_name="q",
                y_unit="kN/m",
                scale=1.0e3,
                title="PFC2D 线载荷–机械时间",
                reason="Frame-aligned native mechanical time and derived PFC2D line load.",
                color=COLOR["primary"],
                source_channel="sample.axial_load_per_unit_thickness",
                chart_name="line_load_time",
            ),
            _candidate_time_response(
                case,
                case_id,
                y_key="frame_speed_mean_m_s",
                y_name="平均速度",
                y_unit="m/s",
                scale=1.0,
                title="平均速度–机械时间",
                reason="Backward finite differences between consecutive real same-ID observations.",
                color=COLOR["slate"],
                source_channel="ball.velocity",
                chart_name="speed_time",
            ),
            _candidate_time_response(
                case,
                case_id,
                y_key="frame_acceleration_mean_m_s2",
                y_name="平均加速度",
                y_unit="m/s^2",
                scale=1.0,
                title="平均加速度–机械时间",
                reason="Backward finite differences between consecutive real same-ID velocity observations.",
                color=COLOR["accent"],
                source_channel="ball.acceleration",
                chart_name="acceleration_time",
            ),
            _candidate_motion_cracks(case, case_id),
            _candidate_motion(case, case_id),
            _candidate_histogram(case, case_id),
            _candidate_particle_size(case, case_id),
            _candidate_rose(case, case_id),
            _candidate_particle_orientation(case, case_id),
            _candidate_density(case, case_id),
            _candidate_spatial_strain(case, case_id),
            _candidate_correlation(case, case_id),
        ]
        for chart in candidates:
            if chart is None:
                continue
            if (
                isinstance(chart.get("x"), dict)
                and isinstance(chart.get("y"), dict)
            ):
                _with_xy_display(chart)
            elif "series" in chart:
                _with_series_display(chart)
            _with_axis_contract(chart)
            _finalize_selected_chart(chart)
            charts.append(chart)
    charts.extend(_case_comparison_charts(comparison))
    _apply_overrides(charts, overrides)
    for chart in charts:
        if "chart_id" not in chart:
            _finalize_selected_chart(chart)
    rejected = _rejected_conditions(cases, comparison)
    rejected_by_id = {item["id"]: item for item in rejected}
    for item in rejected_by_id.values():
        _finalize_rejected_chart(item)
    return {
        "status": "GENERATED" if charts else "NOT_GENERATED",
        "charts": charts,
        "rejected": list(rejected_by_id.values()),
        "decision_policy": {
            "requires_real_data": True,
            "requires_valid_samples": True,
            "requires_explicit_physical_meaning": True,
            "minimum_points_enforced": True,
            "duplicate_and_misleading_candidates_excluded": True,
            "manual_overrides_supported": True,
            "candidate_contract": [
                "chart_id",
                "chart_type",
                "case_id",
                "source_variables",
                "source_data",
                "physical_meaning",
                "unit",
                "selection_reason",
                "omission_reason",
                "data_quality",
                "publication_priority",
            ],
        },
        "chart_type_registry": CHART_TYPES,
        "channel_features": CHANNEL_FEATURES,
    }
