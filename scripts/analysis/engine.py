"""General analysis engine driven by captured fields and explicit formulas."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .channels import CHANNEL_REGISTRY
from .intelligence import select_chart_decisions


class AnalysisError(RuntimeError):
    pass


_COMPARISON_METRICS = (
    {
        "key": "stress_max_pa",
        "unit": "Pa",
        "source_channel": "sample.axial_stress",
        "statistic": "max",
    },
    {
        "key": "strain_max",
        "unit": "1",
        "source_channel": "sample.axial_strain",
        "statistic": "max",
    },
    {
        "key": "displacement_mean_m",
        "unit": "m",
        "source_channel": "ball.displacement",
        "statistic": "mean",
    },
    {
        "key": "crack_final",
        "unit": "event",
        "source_channel": "fracture.cumulative",
        "final_series": "crack_count_cumulative",
    },
)


def _json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _case_arrays_path(experiment_root: Path, case: dict[str, Any]) -> Path:
    path = Path(case["arrays_path"])
    return path if path.is_absolute() else experiment_root / path


def load_standardized_case(experiment_root: Path, case: dict[str, Any]) -> dict[str, np.ndarray]:
    path = _case_arrays_path(experiment_root, case)
    if not path.is_file():
        raise AnalysisError(f"Standardized array file is missing: {path}")
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def _per_entity_position_history(arrays: dict[str, np.ndarray]) -> tuple[np.ndarray, list[np.ndarray]]:
    ids = arrays["ball_id"]
    xyz = arrays["ball_xyz"]
    frame_index = arrays["ball_frame_index"]
    frame_count = len(arrays["cycle"])
    first_seen: dict[int, np.ndarray] = {}
    displacement = np.full(xyz.shape, np.nan, dtype=np.float64)
    distance = np.full(xyz.shape[0], np.nan, dtype=np.float64)
    for row, (entity_id, position, frame) in enumerate(zip(ids, xyz, frame_index)):
        key = int(entity_id)
        if key not in first_seen:
            first_seen[key] = position.copy()
        delta = position - first_seen[key]
        displacement[row] = delta
        distance[row] = float(np.linalg.norm(delta))
    per_frame = [
        np.asarray([], dtype=np.float64) for _ in range(frame_count)
    ]
    for row, frame in enumerate(frame_index):
        per_frame[int(frame)] = np.append(per_frame[int(frame)], distance[row])
    return displacement, per_frame


def _entity_velocity(
    arrays: dict[str, np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    ids = arrays["ball_id"]
    xyz = arrays["ball_xyz"]
    frame_index = arrays["ball_frame_index"]
    times = arrays["mechanical_time_total"]
    velocity = np.full(xyz.shape, np.nan, dtype=np.float64)
    speed = np.full(xyz.shape[0], np.nan, dtype=np.float64)
    by_id: dict[int, list[tuple[int, int]]] = {}
    for row, (entity_id, frame) in enumerate(zip(ids, frame_index)):
        by_id.setdefault(int(entity_id), []).append((row, int(frame)))
    for observations in by_id.values():
        observations.sort(key=lambda item: item[1])
        for (left_row, left_frame), (right_row, right_frame) in zip(
            observations, observations[1:]
        ):
            dt = float(times[right_frame] - times[left_frame])
            if dt <= 0:
                continue
            value = (xyz[right_row] - xyz[left_row]) / dt
            velocity[right_row] = value
            speed[right_row] = float(np.linalg.norm(value))
    return velocity, speed


def _entity_acceleration(
    velocity: np.ndarray, arrays: dict[str, np.ndarray]
) -> np.ndarray:
    ids = arrays["ball_id"]
    frame_index = arrays["ball_frame_index"]
    times = arrays["mechanical_time_total"]
    acceleration = np.full(velocity.shape, np.nan, dtype=np.float64)
    by_id: dict[int, list[tuple[int, int]]] = {}
    for row, (entity_id, frame) in enumerate(zip(ids, frame_index)):
        by_id.setdefault(int(entity_id), []).append((row, int(frame)))
    for observations in by_id.values():
        observations.sort(key=lambda item: item[1])
        for (left_row, left_frame), (right_row, right_frame) in zip(
            observations, observations[1:]
        ):
            if not np.all(np.isfinite(velocity[left_row])) or not np.all(
                np.isfinite(velocity[right_row])
            ):
                continue
            dt = float(times[right_frame] - times[left_frame])
            if dt > 0:
                acceleration[right_row] = (
                    velocity[right_row] - velocity[left_row]
                ) / dt
    return acceleration


def _frame_mean_per_max(values: Iterable[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    mean = []
    maximum = []
    for block in values:
        finite = np.asarray(block, dtype=np.float64)
        finite = finite[np.isfinite(finite)]
        mean.append(float(finite.mean()) if len(finite) else np.nan)
        maximum.append(float(finite.max()) if len(finite) else np.nan)
    return np.asarray(mean), np.asarray(maximum)


def _stats(values: np.ndarray) -> dict[str, Any]:
    array = np.asarray(values, dtype=np.float64)
    finite = array[np.isfinite(array)]
    if len(finite) == 0:
        return {"status": "NOT_CAPTURED", "count": 0}
    return {
        "status": "GENERATED",
        "count": int(len(finite)),
        "mean": float(finite.mean()),
        "min": float(finite.min()),
        "max": float(finite.max()),
        "std": float(finite.std()),
        "q05": float(np.quantile(finite, 0.05)),
        "median": float(np.quantile(finite, 0.50)),
        "q95": float(np.quantile(finite, 0.95)),
    }


def _histogram(values: np.ndarray, bins: int = 32) -> dict[str, Any]:
    source = np.asarray(values, dtype=np.float64)
    finite = source[np.isfinite(source)]
    if len(finite) == 0:
        return {
            "status": "NOT_CAPTURED",
            "counts": [],
            "edges": [],
            "bins": [],
            "labels": [],
            "total_count": int(source.size),
            "finite_count": 0,
            "missing_count": int(source.size),
            "range_policy": "ROBUST_P05_P95_WITH_OVERFLOW",
        }
    q05, q95 = (float(value) for value in np.quantile(finite, [0.05, 0.95]))
    underflow = finite[finite < q05]
    overflow = finite[finite > q95]
    interior = finite[(finite >= q05) & (finite <= q95)]
    bin_count = min(bins, max(5, len(interior)))
    if q95 > q05 and len(interior):
        interior_counts, interior_edges = np.histogram(
            interior, bins=bin_count, range=(q05, q95)
        )
        centers = [
            float((left + right) * 0.5)
            for left, right in zip(interior_edges[:-1], interior_edges[1:])
        ]
        bin_records = [
            {
                "kind": "INTERIOR",
                "index": index,
                "lower": float(interior_edges[index]),
                "upper": float(interior_edges[index + 1]),
                "count": int(count),
            }
            for index, count in enumerate(interior_counts)
        ]
        labels: list[Any] = [
            "< P05",
            *centers,
            "> P95",
        ]
    else:
        interior_counts = np.asarray([len(interior)], dtype=np.int64)
        interior_edges = np.asarray([q05, q95], dtype=np.float64)
        centers = [q05]
        bin_records = [
            {
                "kind": "INTERIOR",
                "index": 0,
                "lower": q05,
                "upper": q95,
                "count": int(len(interior)),
            }
        ]
        labels = ["< P05", q05, "> P95"]
    underflow_count = int(len(underflow))
    overflow_count = int(len(overflow))
    bin_records = [
        {
            "kind": "UNDERFLOW",
            "index": 0,
            "lower": float(finite.min()),
            "upper": q05,
            "count": underflow_count,
        },
        *bin_records,
        {
            "kind": "OVERFLOW",
            "index": len(interior_counts) + 1,
            "lower": q95,
            "upper": float(finite.max()),
            "count": overflow_count,
        },
    ]
    counts = [
        underflow_count,
        *(int(value) for value in interior_counts),
        overflow_count,
    ]
    return {
        "status": "GENERATED",
        "counts": counts,
        "edges": [float(value) for value in interior_edges],
        "bins": bin_records,
        "labels": labels,
        "total_count": int(source.size),
        "finite_count": int(len(finite)),
        "missing_count": int(source.size - len(finite)),
        "underflow_count": underflow_count,
        "overflow_count": overflow_count,
        "interior_quantiles": [0.05, 0.95],
        "interior_min": q05,
        "interior_max": q95,
        "observed_min": float(finite.min()),
        "observed_max": float(finite.max()),
        "interior_bin_count": int(len(interior_counts)),
        "range_policy": "ROBUST_P05_P95_WITH_OVERFLOW",
        "mapping": (
            "All finite observations are assigned exactly once: values below "
            "P05 and above P95 use explicit overflow bins."
        ),
    }


def _correlation_matrix(names: list[str], series: list[np.ndarray]) -> dict[str, Any]:
    usable = []
    for name, values in zip(names, series):
        array = np.asarray(values, dtype=np.float64)
        if len(array) >= 3 and np.isfinite(array).sum() >= 3:
            usable.append((name, array))
    if len(usable) < 2:
        return {"status": "NOT_GENERATED", "reason": "Fewer than two finite channels"}
    length = min(len(value) for _, value in usable)
    matrix = np.vstack([value[:length] for _, value in usable]).T
    finite_rows = np.isfinite(matrix).all(axis=1)
    matrix = matrix[finite_rows]
    if len(matrix) < 3:
        return {"status": "NOT_GENERATED", "reason": "Too few aligned finite rows"}
    variable = np.std(matrix, axis=0) > 1.0e-15
    labels = [name for name, keep in zip([name for name, _ in usable], variable) if keep]
    matrix = matrix[:, variable]
    if len(labels) < 2:
        return {"status": "NOT_GENERATED", "reason": "Fewer than two variable channels"}
    corr = np.corrcoef(matrix, rowvar=False)
    return {
        "status": "GENERATED",
        "labels": labels,
        "values": [[float(value) for value in row] for row in corr],
        "sample_count": int(len(matrix)),
        "method": "Pearson correlation on frame-aligned native samples; no interpolation",
    }


def _json_numbers(values: Any) -> list[float | None]:
    result: list[float | None] = []
    for value in np.asarray(values, dtype=np.float64).tolist():
        result.append(float(value) if math.isfinite(float(value)) else None)
    return result


def _spatial_heatmap(arrays: dict[str, np.ndarray], bins: int = 24) -> dict[str, Any]:
    offsets = arrays["frame_offsets"]
    if len(offsets) < 2:
        return {"status": "NOT_GENERATED"}
    start, end = int(offsets[-2]), int(offsets[-1])
    xyz = arrays["ball_xyz"][start:end]
    if len(xyz) < 2:
        return {"status": "NOT_GENERATED"}
    x, y = xyz[:, 0], xyz[:, 1]
    image, xedges, yedges = np.histogram2d(x, y, bins=bins)
    return {
        "status": "GENERATED",
        "x_edges": [float(value) for value in xedges],
        "y_edges": [float(value) for value in yedges],
        "counts": [[int(value) for value in row] for row in image],
        "boundary": "Particle-count density of the final captured frame; not a physical field.",
    }


def _spatial_declared_field(
    arrays: dict[str, np.ndarray], key: str, unit: str, method: str, bins: int = 24
) -> dict[str, Any]:
    """Bin a declared per-Ball field onto the final-frame XY grid.

    The field must already exist as a declared channel in the NPZ. This helper
    never interprets density, displacement or an unlabelled History as strain;
    it only spatially aggregates an explicitly declared quantity.
    """
    if key not in arrays:
        return {"status": "NOT_CAPTURED"}
    offsets = arrays["frame_offsets"]
    if len(offsets) < 2:
        return {"status": "NOT_GENERATED"}
    start, end = int(offsets[-2]), int(offsets[-1])
    values = arrays[key]
    if values.ndim != 1 or len(values) != len(arrays["ball_id"]):
        return {"status": "INVALID"}
    xyz = arrays["ball_xyz"][start:end]
    vals = values[start:end]
    finite = np.isfinite(vals)
    if len(xyz) < 2 or not finite.any():
        return {"status": "NOT_GENERATED"}
    x, y = xyz[:, 0], xyz[:, 1]
    xedges = np.linspace(float(x.min()), float(x.max()), bins + 1)
    yedges = np.linspace(float(y.min()), float(y.max()), bins + 1)
    total = np.zeros((bins, bins), dtype=np.float64)
    count = np.zeros((bins, bins), dtype=np.float64)
    xi = np.clip(np.digitize(x, xedges) - 1, 0, bins - 1)
    yi = np.clip(np.digitize(y, yedges) - 1, 0, bins - 1)
    for ix, iy, value in zip(xi, yi, vals):
        if np.isfinite(value):
            total[ix, iy] += float(value)
            count[ix, iy] += 1.0
    with np.errstate(invalid="ignore", divide="ignore"):
        image = np.where(count > 0, total / count, np.nan)
    return {
        "status": "GENERATED",
        "x_edges": [float(v) for v in xedges],
        "y_edges": [float(v) for v in yedges],
        "values": [[float(v) if np.isfinite(v) else None for v in row] for row in image],
        "unit": unit,
        "method": method,
        "source_channel": key,
    }


def _derive_case(case: dict[str, Any], arrays: dict[str, np.ndarray]) -> tuple[dict[str, np.ndarray], dict[str, Any], list[dict[str, Any]]]:
    derived = dict(arrays)
    channels = []
    notes = []
    displacement, per_frame_displacement = _per_entity_position_history(arrays)
    derived["ball_displacement_xyz"] = displacement
    displacement_magnitude = np.full(displacement.shape[0], np.nan, dtype=np.float64)
    finite_displacement = np.isfinite(displacement).all(axis=1)
    displacement_magnitude[finite_displacement] = np.linalg.norm(
        displacement[finite_displacement], axis=1
    )
    derived["ball_displacement_magnitude"] = displacement_magnitude
    displacement_mean, displacement_max = _frame_mean_per_max(per_frame_displacement)
    derived["frame_displacement_mean_m"] = displacement_mean
    derived["frame_displacement_max_m"] = displacement_max
    channels.append(
        {
            "id": "ball.displacement",
            "source": "DERIVED",
            "status": "GENERATED",
            "formula": "||x_i(t)-x_i(t_first_observed)||",
            "inputs": ["ball_id", "ball_xyz", "ball_frame_index"],
            "unit": "m",
            "applicability": "A newly observed Ball uses its first real observation as reference.",
        }
    )
    velocity, speed = _entity_velocity(arrays)
    acceleration = _entity_acceleration(velocity, arrays)
    acceleration_norm = np.full(acceleration.shape[0], np.nan, dtype=np.float64)
    finite_acceleration = np.isfinite(acceleration).all(axis=1)
    acceleration_norm[finite_acceleration] = np.linalg.norm(
        acceleration[finite_acceleration], axis=1
    )
    derived["ball_velocity_xyz"] = velocity
    derived["ball_speed_m_s"] = speed
    derived["ball_acceleration_xyz"] = acceleration
    derived["ball_acceleration_magnitude"] = acceleration_norm
    per_speed = [np.asarray([], dtype=np.float64) for _ in range(len(arrays["cycle"]))]
    per_acc = [np.asarray([], dtype=np.float64) for _ in range(len(arrays["cycle"]))]
    for row, frame in enumerate(arrays["ball_frame_index"]):
        if np.isfinite(speed[row]):
            per_speed[int(frame)] = np.append(per_speed[int(frame)], speed[row])
        if np.isfinite(acceleration_norm[row]):
            per_acc[int(frame)] = np.append(per_acc[int(frame)], acceleration_norm[row])
    speed_mean, speed_max = _frame_mean_per_max(per_speed)
    acc_mean, acc_max = _frame_mean_per_max(per_acc)
    derived["frame_speed_mean_m_s"] = speed_mean
    derived["frame_speed_max_m_s"] = speed_max
    derived["frame_acceleration_mean_m_s2"] = acc_mean
    derived["frame_acceleration_max_m_s2"] = acc_max
    channels.extend(
        [
            {
                "id": "ball.velocity",
                "source": "DERIVED",
                "status": "GENERATED" if np.isfinite(speed).any() else "INVALID",
                "formula": "(x(t2)-x(t1))/(t2-t1)",
                "inputs": ["ball_id", "ball_xyz", "mechanical_time_total"],
                "unit": "m/s",
                "applicability": "Backward difference between consecutive real observations of the same ID.",
            },
            {
                "id": "ball.acceleration",
                "source": "DERIVED",
                "status": "GENERATED" if np.isfinite(acceleration_norm).any() else "INVALID",
                "formula": "(v(t2)-v(t1))/(t2-t1)",
                "inputs": ["ball.velocity", "mechanical_time_total"],
                "unit": "m/s^2",
                "applicability": "At least three consecutive observations of the same ID.",
            },
        ]
    )

    frame_count = len(arrays["cycle"])
    ball_count = np.diff(arrays["frame_offsets"])
    derived["ball_count"] = ball_count
    event_cycle = arrays["fracture_event_id"]
    event_cycles = arrays["fracture_cycle"]
    cumulative = np.asarray(
        [int(np.count_nonzero(event_cycles <= cycle)) for cycle in arrays["cycle"]],
        dtype=np.int64,
    )
    tension = np.asarray(
        [
            int(
                np.count_nonzero(
                    (event_cycles <= cycle) & (arrays["fracture_mode"] == 1)
                )
            )
            for cycle in arrays["cycle"]
        ],
        dtype=np.int64,
    )
    shear = cumulative - tension
    derived["crack_count_cumulative"] = cumulative
    derived["crack_tension_cumulative"] = tension
    derived["crack_shear_cumulative"] = shear
    channels.append(
        {
            "id": "fracture.cumulative",
            "source": "DERIVED",
            "status": "GENERATED" if len(event_cycle) else "NOT_CAPTURED",
            "formula": "count(real fracture event with cycle <= frame cycle)",
            "inputs": ["fracture_cycle", "fracture_mode"],
            "unit": "event",
            "applicability": "Only events actually captured; no zero-filled missing channel.",
        }
    )

    geometry = case.get("metadata", {}).get("geometry")
    if geometry and "platen_distance_m" in arrays:
        height = arrays["platen_distance_m"]
        strain = (float(geometry["height0"]) - height) / float(geometry["height0"])
        derived["axial_strain"] = strain
        channels.append(
            {
                "id": "sample.axial_strain",
                "source": "DERIVED",
                "status": "GENERATED" if np.isfinite(strain).any() else "INVALID",
                "formula": "(H0-H)/H0",
                "inputs": ["platen_distance_m", "initial height"],
                "unit": "1",
                "applicability": "Compression-positive engineering strain.",
            }
        )
        if "top_force_n" in arrays and "bottom_force_n" in arrays:
            load = 0.5 * (arrays["top_force_n"] + arrays["bottom_force_n"])
            derived["mean_axial_load_n"] = load
            channels.append(
                {
                    "id": "sample.mean_axial_load",
                    "source": "DERIVED",
                    "status": "GENERATED" if np.isfinite(load).any() else "INVALID",
                    "formula": "0.5*(|F_top|+|F_bottom|)",
                    "inputs": ["top_force_n", "bottom_force_n"],
                    "unit": "N",
                    "applicability": "Requires both platen force channels.",
                }
            )
            if int(geometry.get("dimension", 3)) == 2:
                line_load = load / float(geometry["area0"])
                derived["axial_load_per_unit_thickness_n_m"] = line_load
                channels.append(
                    {
                        "id": "sample.axial_load_per_unit_thickness",
                        "source": "DERIVED",
                        "status": "GENERATED" if np.isfinite(line_load).any() else "INVALID",
                        "formula": "mean_axial_load/W0",
                        "inputs": ["mean_axial_load_n", "PFC2D initial transverse width"],
                        "unit": "N/m",
                        "applicability": "PFC2D line load per unit out-of-plane thickness; not stress in Pa.",
                    }
                )
            else:
                stress = load / float(geometry["area0"])
                derived["axial_stress_pa"] = stress
                channels.append(
                    {
                        "id": "sample.axial_stress",
                        "source": "DERIVED",
                        "status": "GENERATED" if np.isfinite(stress).any() else "INVALID",
                        "formula": "mean_axial_load/A0",
                        "inputs": ["mean_axial_load_n", "initial cross-section area"],
                        "unit": "Pa",
                        "applicability": "Nominal engineering stress, not a native PFC stress tensor.",
                    }
                )

    # Declared MOCK extension channels. These are read only when explicitly
    # present in the standardized NPZ; no value is fabricated or inferred.
    extension_channels = []
    if "ball_contact_force_n" in arrays:
        derived["ball_contact_force_n"] = arrays["ball_contact_force_n"]
        extension_channels.append({
            "id": "ball.contact_force",
            "source": "DECLARED_MOCK",
            "status": "GENERATED",
            "formula": None,
            "inputs": ["ball_contact_force_n"],
            "unit": "N",
            "applicability": "Declared extension channel; MOCK values only.",
        })
    if "ball_orientation_deg" in arrays:
        derived["ball_orientation_deg"] = arrays["ball_orientation_deg"]
        extension_channels.append({
            "id": "ball.orientation",
            "source": "DECLARED_MOCK",
            "status": "GENERATED",
            "formula": None,
            "inputs": ["ball_orientation_deg"],
            "unit": "degree",
            "applicability": "Declared extension channel; MOCK values only.",
        })
    if "ball_strain_local" in arrays:
        derived["ball_strain_local"] = arrays["ball_strain_local"]
        extension_channels.append({
            "id": "ball.local_strain",
            "source": "DECLARED_MOCK",
            "status": "GENERATED",
            "formula": None,
            "inputs": ["ball_strain_local"],
            "unit": "1",
            "applicability": "Declared extension channel; MOCK values only.",
        })
    channels.extend(extension_channels)

    orientation = {}
    if len(arrays["fracture_event_id"]):
        normals = arrays["fracture_normal"]
        finite = normals[np.isfinite(normals).all(axis=1)]
        if len(finite):
            dip = np.degrees(np.arccos(np.clip(np.abs(finite[:, 2]), 0, 1)))
            azimuth = (np.degrees(np.arctan2(finite[:, 1], finite[:, 0])) + 360.0) % 360.0
            orientation = {
                "status": "GENERATED",
                "dip_deg": [float(value) for value in dip],
                "azimuth_deg": [float(value) for value in azimuth],
                "method": "Derived from captured fracture normal; no orientation is guessed.",
            }

    # Particle orientation rose from the DECLARED per-Ball orientation channel.
    ball_orientation = {}
    if "ball_orientation_deg" in arrays:
        offsets = arrays["frame_offsets"]
        start, end = int(offsets[-2]), int(offsets[-1])
        angles = arrays["ball_orientation_deg"][start:end]
        angles = angles[np.isfinite(angles)] % 180.0
        if len(angles):
            edges = np.linspace(0.0, 180.0, 7)
            counts, _ = np.histogram(angles, bins=edges)
            total = int(counts.sum())
            ball_orientation = {
                "status": "GENERATED",
                "edges_deg": [float(v) for v in edges],
                "counts": [int(v) for v in counts],
                "percent": [round(100.0 * v / total, 2) for v in counts] if total else [],
                "method": "Declared per-Ball orientation binned into 6 sectors of the final frame.",
                "source_channel": "ball_orientation_deg",
            }

    series = {
        "cycle": arrays["cycle"],
        "mechanical_time_total": arrays["mechanical_time_total"],
        "ball_count": ball_count,
        "frame_displacement_mean_m": displacement_mean,
        "frame_displacement_max_m": displacement_max,
        "frame_speed_mean_m_s": speed_mean,
        "frame_speed_max_m_s": speed_max,
        "frame_acceleration_mean_m_s2": acc_mean,
        "frame_acceleration_max_m_s2": acc_max,
        "crack_count_cumulative": cumulative,
        "crack_tension_cumulative": tension,
        "crack_shear_cumulative": shear,
    }
    for key in (
        "axial_strain",
        "axial_stress_pa",
        "axial_load_per_unit_thickness_n_m",
        "mean_axial_load_n",
    ):
        if key in derived:
            series[key] = derived[key]
    channel_names = [
        key
        for key in (
            "mechanical_time_total",
            "ball_count",
            "frame_displacement_mean_m",
            "frame_speed_mean_m_s",
            "frame_acceleration_mean_m_s2",
            "crack_count_cumulative",
            "axial_strain",
            "axial_stress_pa",
            "axial_load_per_unit_thickness_n_m",
        )
        if key in series
    ]
    correlation = _correlation_matrix(
        channel_names, [np.asarray(series[key], dtype=np.float64) for key in channel_names]
    )
    result = {
        "status": "GENERATED",
        "case_id": int(case["case_id"]),
        "dimension": int(case["dimension"]),
        "frame_count": frame_count,
        "crack_available": bool(len(event_cycle)),
        "channels": channels,
        "statistics": {
            "displacement_m": _stats(derived["ball_displacement_magnitude"]),
            "speed_m_s": _stats(speed),
            "acceleration_m_s2": _stats(acceleration_norm),
            "ball_count": _stats(ball_count),
            "axial_strain": _stats(derived["axial_strain"]) if "axial_strain" in derived else {"status": "NOT_CAPTURED"},
            "axial_stress_pa": _stats(derived["axial_stress_pa"]) if "axial_stress_pa" in derived else {"status": "NOT_CAPTURED"},
            "axial_load_per_unit_thickness_n_m": _stats(derived["axial_load_per_unit_thickness_n_m"]) if "axial_load_per_unit_thickness_n_m" in derived else {"status": "NOT_CAPTURED"},
        },
        "histograms": {
            "final_displacement_m": _histogram(
                derived["ball_displacement_magnitude"][
                    int(arrays["frame_offsets"][-2]) : int(arrays["frame_offsets"][-1])
                ]
            ),
            "final_speed_m_s": _histogram(
                speed[int(arrays["frame_offsets"][-2]) : int(arrays["frame_offsets"][-1])]
            ),
            "particle_radius_m": _histogram(
                arrays["ball_radius"][
                    int(arrays["frame_offsets"][-2]) : int(arrays["frame_offsets"][-1])
                ]
            ) if "ball_radius" in arrays else {"status": "NOT_CAPTURED"},
        },
        "orientation": orientation,
        "ball_orientation": ball_orientation,
        "spatial_density": _spatial_heatmap(arrays),
        "spatial_strain": _spatial_declared_field(
            arrays, "ball_strain_local", "1",
            "Declared per-Ball local strain binned onto final-frame XY grid; MOCK values."
        ),
        "correlation": correlation,
        "series": {key: _json_numbers(value) for key, value in series.items()},
        "unsupported_or_missing": [
            {
                "channel": name,
                "status": "NOT_CAPTURED",
                "reason": spec["requirements"],
            }
            for name, spec in CHANNEL_REGISTRY.items()
            if (
                (
                    name.startswith("contact.")
                    and not any(key.startswith("contact_") for key in arrays)
                )
                or (
                    name.startswith("bond.")
                    and not any(key.startswith("bond_") for key in arrays)
                )
                or (name.startswith("fracture.") and not len(event_cycle) and name != "fracture.cumulative")
            )
        ],
        "notes": notes,
    }
    return derived, result, channels


def _case_comparison(analyses: list[dict[str, Any]]) -> dict[str, Any]:
    if len(analyses) < 2:
        return {"status": "NOT_GENERATED", "reason": "A comparison requires at least two cases."}
    points_by_case = {
        int(item["case_id"]): {"case_id": int(item["case_id"])}
        for item in analyses
    }
    metrics: dict[str, Any] = {}
    statistics_keys = {
        "stress_max_pa": "axial_stress_pa",
        "strain_max": "axial_strain",
        "displacement_mean_m": "displacement_m",
    }
    for definition in _COMPARISON_METRICS:
        key = str(definition["key"])
        metric_cases = []
        for item in analyses:
            case_id = int(item["case_id"])
            value: float | None = None
            source_status = "NOT_CAPTURED"
            reason = None
            if "statistic" in definition:
                statistics = item.get("statistics", {}).get(
                    statistics_keys[key], {}
                )
                source_status = str(statistics.get("status", "NOT_CAPTURED"))
                candidate = statistics.get(definition["statistic"])
                try:
                    number = float(candidate) if candidate is not None else None
                except (TypeError, ValueError):
                    number = None
                if (
                    source_status == "GENERATED"
                    and number is not None
                    and math.isfinite(number)
                ):
                    value = number
                elif source_status == "GENERATED":
                    source_status = "INVALID"
            else:
                series = item.get("series", {}).get(
                    str(definition["final_series"]), []
                )
                if item.get("crack_available") and series:
                    candidate = series[-1]
                    try:
                        number = (
                            float(candidate) if candidate is not None else None
                        )
                    except (TypeError, ValueError):
                        number = None
                    if number is not None and math.isfinite(number):
                        value = number
                        source_status = "GENERATED"
                    else:
                        source_status = "INVALID"
            if value is None:
                reason = f"{definition['source_channel']}:{source_status}"
            state = "AVAILABLE" if value is not None else source_status
            metric_cases.append(
                {
                    "case_id": case_id,
                    "value": value,
                    "state": state,
                    "reason": reason,
                }
            )
            points_by_case[case_id][key] = value
        available_count = sum(
            item["value"] is not None for item in metric_cases
        )
        missing_case_ids = [
            int(item["case_id"])
            for item in metric_cases
            if item["value"] is None
        ]
        comparable = available_count >= 2
        if available_count == 0:
            status = "NOT_CAPTURED"
        elif not comparable:
            status = "NOT_GENERATED"
        else:
            status = "GENERATED"
        metrics[key] = {
            "status": status,
            "unit": definition["unit"],
            "source_channel": definition["source_channel"],
            "total_case_count": len(analyses),
            "available_case_count": available_count,
            "missing_case_count": len(missing_case_ids),
            "missing_case_ids": missing_case_ids,
            "comparable": comparable,
            "not_comparable_reason": (
                None
                if comparable
                else "Fewer than two Cases provide a finite native/final value."
            ),
            "cases": metric_cases,
        }
    return {
        "status": "GENERATED",
        "cases": [
            points_by_case[int(item["case_id"])]
            for item in analyses
        ],
        "metrics": metrics,
        "method": "Native per-case summaries; no common-time interpolation.",
        "availability_policy": {
            "missing_is_not_zero": True,
            "counts_are_explicit": True,
            "minimum_comparable_cases": 2,
        },
    }


def analyze_experiment(
    experiment_root: Path,
    output_root: Path,
    *,
    chart_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    experiment_root = experiment_root.resolve()
    output_root = output_root.resolve()
    experiment = json.loads(
        (experiment_root / "experiment.json").read_text(encoding="utf-8")
    )
    analyses = []
    derived_cases = {}
    for case in experiment["cases"]:
        arrays = load_standardized_case(experiment_root, case)
        derived, result, channels = _derive_case(case, arrays)
        derived_cases[int(case["case_id"])] = derived
        case_output = output_root / f"case_{case['case_id']}"
        case_output.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(case_output / "analysis_arrays.npz", **derived)
        _json_dump(case_output / "analysis.json", result)
        analyses.append(result)
    comparison = _case_comparison(analyses)
    chart_decisions = select_chart_decisions(
        analyses,
        comparison,
        overrides=chart_overrides,
    )
    chart_specs = chart_decisions["charts"]
    payload = {
        "status": "GENERATED",
        "data_boundary": experiment.get("data_boundary"),
        "cases": analyses,
        "comparison": comparison,
        "charts": chart_specs,
        "chart_decision_summary": {
            "status": chart_decisions["status"],
            "selected_count": len(chart_specs),
            "rejected_count": len(chart_decisions["rejected"]),
            "policy": chart_decisions["decision_policy"],
        },
        "definitions": CHANNEL_REGISTRY,
        "truth_policy": {
            "missing_data": "NOT_CAPTURED",
            "interpolation": "FORBIDDEN",
            "zero_fill": "FORBIDDEN",
            "derived_requires_inputs": True,
        },
    }
    _json_dump(output_root / "analysis.json", payload)
    _json_dump(output_root / "chart_specs.json", chart_specs)
    _json_dump(output_root / "chart_decisions.json", chart_decisions)
    return payload
