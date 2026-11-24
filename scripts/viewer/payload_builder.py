"""Build a chunked, browser-loadable Viewer payload from standardized data.

The payload is deliberately separate from the Viewer shell. A styling-only
Viewer rebuild can therefore reuse this directory without reopening PFC files
or converting the per-frame arrays again.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import shutil
import time
from pathlib import Path
from typing import Any, Iterable

import numpy as np


PAYLOAD_VERSION = "2.2.0"
CHUNK_FRAMES = 8
HISTORY_BUCKETS = 128
MARKER = ".pfc-generated"


class PayloadBuildError(RuntimeError):
    pass


def _json_text(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).replace("</", "<\\/")


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def _write_json(path: Path, value: Any) -> None:
    _write_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def _encode_u32(values: np.ndarray) -> str:
    return base64.b64encode(np.asarray(values, dtype="<u4").tobytes()).decode("ascii")


def _encode_f32(values: np.ndarray) -> str:
    return base64.b64encode(np.asarray(values, dtype="<f4").tobytes()).decode("ascii")


def _finite_or_none(value: Any) -> float | None:
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _case_arrays_path(experiment_root: Path, case: dict[str, Any]) -> Path:
    path = Path(case["arrays_path"])
    return path if path.is_absolute() else experiment_root / path


def _selected_indices(count: int, limit: int | None) -> list[int]:
    if count <= 0:
        return []
    if limit is None or limit <= 0 or count <= limit:
        return list(range(count))
    if limit < 2:
        raise PayloadBuildError("max_frames must be zero (all frames) or at least 2")
    return sorted({round(index * (count - 1) / (limit - 1)) for index in range(limit)})


def _normalize(vector: np.ndarray) -> np.ndarray | None:
    array = np.asarray(vector, dtype=np.float64)
    length = float(np.linalg.norm(array))
    if not math.isfinite(length) or length <= 0:
        return None
    return array / length


def _crack_tangent(normal: np.ndarray) -> np.ndarray | None:
    unit = _normalize(normal)
    if unit is None:
        return None
    reference = np.asarray([0.0, 0.0, 1.0])
    if abs(float(unit[2])) > 0.92:
        reference = np.asarray([1.0, 0.0, 0.0])
    tangent = np.cross(unit, reference)
    if np.linalg.norm(tangent) < 1.0e-10:
        tangent = np.cross(unit, np.asarray([0.0, 1.0, 0.0]))
    return _normalize(tangent)


def _crack_records(arrays: dict[str, np.ndarray]) -> tuple[list[list[float]], str]:
    ids = np.asarray(arrays.get("fracture_event_id", []), dtype=np.int64)
    if len(ids) == 0:
        return [], "NOT_CAPTURED"
    cycles = np.asarray(arrays.get("fracture_cycle", []), dtype=np.int64)
    modes = np.asarray(arrays.get("fracture_mode", []), dtype=np.int8)
    positions = np.asarray(arrays.get("fracture_position", np.zeros((0, 3))))
    normals = np.asarray(arrays.get("fracture_normal", np.zeros((0, 3))))
    diameters = np.asarray(arrays.get("fracture_diameter", []), dtype=np.float64)
    # Optional endpoint Ball IDs.  When the standardized contract carries the
    # two balls whose bond broke, the Viewer can re-anchor the crack segment to
    # their *current* per-frame positions so cracks follow particle motion.
    # Datasets without these fields fall back to the captured static segment
    # (backward compatible with real PFC captures).
    ball_a = np.asarray(arrays.get("fracture_ball_id_a", []), dtype=np.int64)
    ball_b = np.asarray(arrays.get("fracture_ball_id_b", []), dtype=np.int64)
    has_endpoints = len(ball_a) == len(ids) and len(ball_b) == len(ids)
    records: list[list[float]] = []
    for event_index, (event_id, mode, position, normal, diameter) in enumerate(
        zip(ids, modes, positions, normals, diameters)
    ):
        tangent = _crack_tangent(normal)
        if (
            tangent is None
            or not np.isfinite(position).all()
            or not math.isfinite(float(diameter))
            or float(diameter) <= 0
        ):
            continue
        half = float(diameter) * 0.5
        start = position - tangent * half
        end = position + tangent * half
        records.append(
            [
                float(start[0]),
                float(start[1]),
                float(start[2]),
                float(end[0]),
                float(end[1]),
                float(end[2]),
                int(cycles[event_index]),
                1 if int(mode) == 2 else 0,
                int(event_id),
                int(ball_a[event_index]) if has_endpoints else 0,
                int(ball_b[event_index]) if has_endpoints else 0,
            ]
        )
    records.sort(key=lambda row: row[6])
    return records, "GENERATED" if records else "INVALID_GEOMETRY"


def _static_payload(experiment_root: Path, cases: Iterable[dict[str, Any]]) -> dict[str, Any]:
    by_case: dict[str, dict[str, Any]] = {}
    for case in cases:
        path = _case_arrays_path(experiment_root, case).parent / "static.json"
        if not path.is_file():
            continue
        static = json.loads(path.read_text(encoding="utf-8"))
        balls: dict[int, list[float]] = {}
        walls: dict[int, dict[str, Any]] = {}
        for ball in static.get("balls", []):
            ball_id = int(ball["id"])
            balls.setdefault(
                ball_id,
                [
                    ball_id,
                    float(ball["x"]),
                    float(ball["y"]),
                    float(ball["z"]),
                    float(ball.get("radius", 0.0)),
                ],
            )
        for wall in static.get("walls", []):
            wall_id = int(wall["id"])
            entry = walls.setdefault(
                wall_id,
                {
                    "id": wall_id,
                    "name": str(wall.get("name", "")),
                    "_vertices": {},
                    "facets": wall.get("facets", []),
                },
            )
            for vertex in wall.get("vertices", []):
                vertex_id = int(vertex.get("id", len(entry["_vertices"]) + 1))
                position = vertex["position"]
                entry["_vertices"].setdefault(
                    vertex_id,
                    {
                        "id": vertex_id,
                        "position": [
                            float(position[0]),
                            float(position[1]),
                            float(position[2]) if len(position) > 2 else 0.0,
                        ],
                    },
                )
        wall_list = [
            {
                "id": wall["id"],
                "name": wall["name"],
                "vertices": [wall["_vertices"][key] for key in sorted(wall["_vertices"])],
                # PFC3D real facet topology. The static.json written by headless
                # now carries facet.vertex_ids; viewer joins these IDs with the
                # per-frame wall vertex positions to render real faces.
                "facets": [
                    {
                        "id": int(facet.get("id", index + 1)),
                        "vertex_ids": [int(v) for v in facet.get("vertex_ids", [])],
                        "normal": [
                            float(facet.get("normal", [0, 0, 1])[0]),
                            float(facet.get("normal", [0, 0, 1])[1]),
                            float(facet.get("normal", [0, 0, 1])[2]) if len(facet.get("normal", [0, 0, 1])) > 2 else 0.0,
                        ],
                    }
                    for index, facet in enumerate(wall.get("facets", []))
                ],
            }
            for wall in sorted(walls.values(), key=lambda value: value["id"])
        ]
        by_case[str(int(case["case_id"]))] = {
            "balls": [balls[key] for key in sorted(balls)],
            "walls": wall_list,
        }
    first = next(iter(by_case.values()), {"balls": [], "walls": []})
    return {
        "cases": by_case,
        "balls": first["balls"],
        "walls": first["walls"],
    }


def _source_signature(
    experiment_root: Path,
    analysis_root: Path,
    cases: list[dict[str, Any]],
    max_frames: int | None,
) -> list[dict[str, Any]]:
    signatures = []
    for case in cases:
        paths = [
            _case_arrays_path(experiment_root, case),
            analysis_root / f"case_{case['case_id']}" / "analysis_arrays.npz",
            _case_arrays_path(experiment_root, case).parent / "static.json",
        ]
        item: dict[str, Any] = {"case_id": int(case["case_id"]), "files": []}
        for path in paths:
            if path.is_file():
                stat = path.stat()
                item["files"].append(
                    {
                        "path": path.name,
                        "size": int(stat.st_size),
                        "mtime_ns": int(stat.st_mtime_ns),
                    }
                )
            else:
                item["files"].append({"path": path.name, "missing": True})
        signatures.append(item)
    return [
        {
            "payload_version": PAYLOAD_VERSION,
            "max_frames": max_frames or 0,
            "chunk_frames": CHUNK_FRAMES,
            "history_buckets": HISTORY_BUCKETS,
            "cases": signatures,
        }
    ]


def _load_case_arrays(
    experiment_root: Path, analysis_root: Path, case: dict[str, Any]
) -> tuple[np.lib.npyio.NpzFile, np.lib.npyio.NpzFile]:
    arrays_path = _case_arrays_path(experiment_root, case)
    analysis_path = analysis_root / f"case_{case['case_id']}" / "analysis_arrays.npz"
    if not arrays_path.is_file():
        raise PayloadBuildError(f"Standardized arrays missing: {arrays_path}")
    if not analysis_path.is_file():
        raise PayloadBuildError(f"Analysis arrays missing: {analysis_path}")
    return (
        np.load(arrays_path, allow_pickle=False),
        np.load(analysis_path, allow_pickle=False),
    )


def _series_value(
    analysis: np.lib.npyio.NpzFile,
    arrays: np.lib.npyio.NpzFile,
    key: str,
    source_index: int,
) -> float | None:
    if key in analysis.files:
        values = analysis[key]
        if source_index < len(values):
            return _finite_or_none(values[source_index])
    if key in arrays.files:
        values = arrays[key]
        if source_index < len(values):
            return _finite_or_none(values[source_index])
    return None


def _slice_chart(spec: dict[str, Any], indices: list[int], source_count: int) -> dict[str, Any]:
    chart = dict(spec)
    source_indices = spec.get("source_indices")
    if source_indices is None:
        x = spec.get("x")
        temporal = (
            isinstance(x, dict)
            and x.get("unit") in {"s", "cycle"}
        )
        if not temporal:
            chart["compatibility"] = {
                "source_indices": "NOT_REQUIRED_NON_TEMPORAL_CHART"
            }
            return chart
        data_lengths = [
            len(container["data"])
            for container in [x, spec.get("y"), *spec.get("series", [])]
            if isinstance(container, dict) and isinstance(container.get("data"), list)
        ]
        if not data_lengths or any(length != source_count for length in data_lengths):
            raise PayloadBuildError(
                "Legacy temporal chart has no source_indices and cannot be "
                "sliced without positional inference"
            )
        source_indices = list(range(source_count))
        chart["source_indices"] = source_indices
        chart["compatibility"] = {
            "source_indices": "LEGACY_EXACT_FULL_SOURCE_EXTENT",
            "description": (
                "Legacy chart had no explicit indices; the one-to-one mapping "
                "was accepted only because every temporal array exactly spans "
                "the full source frame count."
            ),
        }
    elif "compatibility" not in chart:
        chart["compatibility"] = {"source_indices": "EXPLICIT"}
    if not isinstance(source_indices, list):
        raise PayloadBuildError("Chart source_indices must be a list")
    numeric_indices = [int(value) for value in source_indices]
    if (
        len(set(numeric_indices)) != len(numeric_indices)
        or any(value < 0 or value >= source_count for value in numeric_indices)
    ):
        raise PayloadBuildError("Chart source_indices are invalid")
    position_by_source = {
        source_index: position
        for position, source_index in enumerate(numeric_indices)
    }
    positions = [
        position_by_source[index]
        for index in indices
        if index in position_by_source
    ]
    chart["source_indices"] = [numeric_indices[position] for position in positions]

    def subset(container: dict[str, Any]) -> dict[str, Any]:
        values = container.get("data")
        if values is None:
            return dict(container)
        if not isinstance(values, list) or len(values) != len(numeric_indices):
            raise PayloadBuildError(
                "Chart series length does not match its explicit source_indices"
            )
        replacement = dict(container)
        replacement["data"] = [values[position] for position in positions]
        return replacement

    if "x" in spec:
        chart["x"] = subset(chart["x"])
    if "y" in spec:
        chart["y"] = subset(chart["y"])
    if "series" in spec:
        chart["series"] = []
        for series in spec["series"]:
            item = dict(series)
            values = series.get("data")
            if values is not None and (
                not isinstance(values, list)
                or len(values) != len(numeric_indices)
            ):
                raise PayloadBuildError(
                    "Chart series length does not match its explicit source_indices"
                )
            if isinstance(values, list):
                item["data"] = [values[position] for position in positions]
            chart["series"].append(item)
    if isinstance(spec.get("display"), dict):
        display = {}
        for key, container in spec["display"].items():
            if not isinstance(container, dict):
                display[key] = container
                continue
            item = dict(container)
            values = container.get("values")
            if values is not None and (
                not isinstance(values, list)
                or len(values) != len(numeric_indices)
            ):
                raise PayloadBuildError(
                    "Chart display values do not match explicit source_indices"
                )
            if isinstance(values, list):
                item["values"] = [values[position] for position in positions]
            tooltip = container.get("tooltip_values")
            if tooltip is not None and (
                not isinstance(tooltip, list)
                or len(tooltip) != len(numeric_indices)
            ):
                raise PayloadBuildError(
                    "Chart tooltip values do not match explicit source_indices"
                )
            if isinstance(tooltip, list):
                item["tooltip_values"] = [
                    tooltip[position] for position in positions
                ]
            display[key] = item
        chart["display"] = display
    return chart


def _network_frame_payload(
    arrays: np.lib.npyio.NpzFile,
    prefix: str,
    source_index: int,
) -> dict[str, Any]:
    # Support BOTH field spellings:
    #  * headless converter contract: {prefix}_offsets / _end1_id / _end2_id
    #    with an optional vector force {prefix}_force_xyz (N) -> magnitude;
    #  * legacy/extended contract: {prefix}_frame_offsets / _ball_id_a / _ball_id_b
    #    with optional scalar {prefix}_force_n.
    # resolver returns (offsets_key, first_key, second_key, force_key, force_is_vector)
    resolver = None
    if (
        f"{prefix}_offsets" in arrays.files
        and f"{prefix}_end1_id" in arrays.files
        and f"{prefix}_end2_id" in arrays.files
    ):
        resolver = (
            f"{prefix}_offsets",
            f"{prefix}_end1_id",
            f"{prefix}_end2_id",
            f"{prefix}_force_xyz" if f"{prefix}_force_xyz" in arrays.files else None,
            True,
        )
    elif (
        f"{prefix}_frame_offsets" in arrays.files
        and f"{prefix}_ball_id_a" in arrays.files
        and f"{prefix}_ball_id_b" in arrays.files
    ):
        resolver = (
            f"{prefix}_frame_offsets",
            f"{prefix}_ball_id_a",
            f"{prefix}_ball_id_b",
            f"{prefix}_force_n" if f"{prefix}_force_n" in arrays.files else None,
            False,
        )
    if resolver is None:
        return {}
    offsets_key, first_key, second_key, force_key, force_is_vector = resolver
    offsets = arrays[offsets_key]
    if source_index + 1 >= len(offsets):
        return {}
    start, end = int(offsets[source_index]), int(offsets[source_index + 1])
    if end <= start:
        return {}
    result = {
        "a": _encode_u32(arrays[first_key][start:end]),
        "b": _encode_u32(arrays[second_key][start:end]),
    }
    if force_key in arrays.files:
        if force_is_vector:
            vectors = np.asarray(arrays[force_key][start:end], dtype=np.float64).reshape((-1, 3))
            magnitude = np.linalg.norm(vectors, axis=1)
        else:
            magnitude = np.asarray(arrays[force_key][start:end], dtype=np.float64)
        result["force"] = _encode_f32(np.asarray(magnitude, dtype=np.float32))
    return result


def _write_chunk(
    path: Path,
    case_id: int,
    chunk_index: int,
    frames: list[dict[str, Any]],
) -> int:
    payload = {
        "caseId": int(case_id),
        "chunkIndex": int(chunk_index),
        "encoding": "base64-le-u32/f32",
        "frames": frames,
    }
    text = (
        "window.PFC_VIEWER_DATA.registerChunk("
        + str(int(case_id))
        + ","
        + str(int(chunk_index))
        + ","
        + _json_text(payload)
        + ");\n"
    )
    _write_text(path, text)
    return path.stat().st_size


def _history_payload(
    ball_id: int,
    source_frame_indices: np.ndarray,
    viewer_frame_indices: np.ndarray,
    xyz: np.ndarray,
    displacement: np.ndarray,
    speed: np.ndarray,
    acceleration: np.ndarray,
) -> dict[str, Any]:
    rows = np.column_stack(
        [
            np.asarray(source_frame_indices, dtype=np.float32),
            np.asarray(viewer_frame_indices, dtype=np.float32),
            np.asarray(xyz, dtype=np.float32),
            np.asarray(displacement, dtype=np.float32),
            np.asarray(speed, dtype=np.float32),
            np.asarray(acceleration, dtype=np.float32),
        ]
    )
    return {
        "id": int(ball_id),
        "count": int(len(rows)),
        "data": _encode_f32(rows.reshape(-1)),
    }


def _write_history_bucket(
    path: Path, case_id: int, bucket: int, entries: list[dict[str, Any]]
) -> int:
    text = (
        "window.PFC_VIEWER_DATA.registerHistory("
        + str(int(case_id))
        + ","
        + str(int(bucket))
        + ","
        + _json_text({"entries": entries})
        + ");\n"
    )
    _write_text(path, text)
    return path.stat().st_size


def _write_case_payload(
    experiment_root: Path,
    analysis_root: Path,
    case_data_root: Path,
    case: dict[str, Any],
    analysis: dict[str, Any] | None,
    chart_specs: list[dict[str, Any]],
    max_frames: int | None,
) -> tuple[dict[str, Any], int, int, int]:
    arrays_file, analysis_file = _load_case_arrays(experiment_root, analysis_root, case)
    try:
        source_count = int(len(arrays_file["cycle"]))
        selected = _selected_indices(source_count, max_frames)
        if not selected:
            raise PayloadBuildError(f"Case {case['case_id']} has no real frames")

        cycle = arrays_file["cycle"]
        mechanical_time = arrays_file["mechanical_time_total"]
        offsets = arrays_file["frame_offsets"]
        ball_ids = arrays_file["ball_id"]
        ball_xyz = arrays_file["ball_xyz"]
        ball_radius = arrays_file["ball_radius"]
        ball_frame_index = arrays_file["ball_frame_index"]
        wall_offsets = arrays_file["wall_offsets"]
        wall_ids = arrays_file["wall_id"]
        wall_vertex_ids = arrays_file["wall_vertex_id"]
        wall_vertex_xyz = arrays_file["wall_vertex_xyz"]

        displacement = (
            analysis_file["ball_displacement_magnitude"]
            if "ball_displacement_magnitude" in analysis_file.files
            else np.full(len(ball_ids), np.nan, dtype=np.float32)
        )
        speed = (
            analysis_file["ball_speed_m_s"]
            if "ball_speed_m_s" in analysis_file.files
            else np.full(len(ball_ids), np.nan, dtype=np.float32)
        )
        if "ball_acceleration_magnitude" in analysis_file.files:
            acceleration = analysis_file["ball_acceleration_magnitude"]
        elif "ball_acceleration_xyz" in analysis_file.files:
            acceleration_xyz = np.asarray(
                analysis_file["ball_acceleration_xyz"], dtype=np.float64
            )
            acceleration = np.linalg.norm(acceleration_xyz, axis=1)
        else:
            acceleration = np.full(len(ball_ids), np.nan, dtype=np.float32)
        contact_force = (
            analysis_file["ball_contact_force_n"]
            if "ball_contact_force_n" in analysis_file.files
            else np.full(len(ball_ids), np.nan, dtype=np.float32)
        )
        metric_status = {
            "displacement": (
                "SUPPORTED"
                if int(np.isfinite(displacement).sum()) > 0
                else "NOT_CAPTURED"
            ),
            "speed": (
                "SUPPORTED"
                if int(np.isfinite(speed).sum()) > 0
                else "NOT_CAPTURED"
            ),
            "acceleration": (
                "SUPPORTED"
                if int(np.isfinite(acceleration).sum()) > 0
                else "NOT_CAPTURED"
            ),
            "contactForce": (
                "SUPPORTED"
                if int(np.isfinite(contact_force).sum()) > 0
                else "NOT_CAPTURED"
            ),
        }
        entity_status = {
            "ball": "SUPPORTED" if len(ball_ids) else "NOT_CAPTURED",
            "wall": "SUPPORTED" if len(wall_ids) else "NOT_CAPTURED",
            "fracture": (
                "SUPPORTED"
                if "fracture_event_id" in arrays_file.files
                and len(arrays_file["fracture_event_id"])
                else "NOT_CAPTURED"
            ),
            "contact": (
                "SUPPORTED"
                if any(
                    name.startswith("contact_") and arrays_file[name].size
                    for name in arrays_file.files
                )
                else "NOT_CAPTURED"
            ),
            "bond": (
                "SUPPORTED"
                if any(
                    name.startswith("bond_") and arrays_file[name].size
                    for name in arrays_file.files
                )
                else "NOT_CAPTURED"
            ),
            "clump": "NOT_CAPTURED",
        }
        geometry = case.get("metadata", {}).get("geometry") or {}
        case_id = int(case["case_id"])
        chunk_dir = case_data_root / "chunks"
        frames_meta: list[dict[str, Any]] = []
        pending_frames: list[dict[str, Any]] = []
        chunk_sizes: list[int] = []
        max_displacement = 0.0
        max_speed = 0.0
        max_acceleration = 0.0
        max_contact_force = 0.0
        lo = np.asarray([math.inf, math.inf, math.inf])
        hi = np.asarray([-math.inf, -math.inf, -math.inf])

        for viewer_index, source_index in enumerate(selected):
            start, end = int(offsets[source_index]), int(offsets[source_index + 1])
            ids = ball_ids[start:end]
            xyz = ball_xyz[start:end]
            radii = ball_radius[start:end]
            disp = displacement[start:end]
            speeds = speed[start:end]
            acceleration_values = acceleration[start:end]
            contact_force_values = contact_force[start:end]
            finite_disp = disp[np.isfinite(disp)]
            finite_speed = speeds[np.isfinite(speeds)]
            finite_acceleration = acceleration_values[np.isfinite(acceleration_values)]
            if len(finite_disp):
                max_displacement = max(max_displacement, float(finite_disp.max()))
            if len(finite_speed):
                max_speed = max(max_speed, float(finite_speed.max()))
            if len(finite_acceleration):
                max_acceleration = max(
                    max_acceleration, float(finite_acceleration.max())
                )
            finite_contact = contact_force_values[np.isfinite(contact_force_values)]
            if len(finite_contact):
                max_contact_force = max(max_contact_force, float(finite_contact.max()))
            if len(xyz):
                lo = np.minimum(lo, xyz.min(axis=0))
                hi = np.maximum(hi, xyz.max(axis=0))

            wall_start = int(wall_offsets[source_index])
            wall_end = int(wall_offsets[source_index + 1])
            frame_payload: dict[str, Any] = {
                "sourceIndex": int(source_index),
                "cycle": int(cycle[source_index]),
                "time": float(mechanical_time[source_index]),
                "ballCount": int(len(ids)),
                "ids": _encode_u32(ids),
                "xyz": _encode_f32(np.asarray(xyz, dtype=np.float32)),
                "displacement": _encode_f32(np.asarray(disp, dtype=np.float32)),
                "speed": _encode_f32(np.asarray(speeds, dtype=np.float32)),
                "acceleration": _encode_f32(
                    np.asarray(acceleration_values, dtype=np.float32)
                ),
                "contactForce": _encode_f32(
                    np.asarray(contact_force_values, dtype=np.float32)
                ),
                "radius": _encode_f32(np.asarray(radii, dtype=np.float32)),
            }
            contact_payload = _network_frame_payload(arrays_file, "contact", source_index)
            if contact_payload:
                frame_payload["contacts"] = contact_payload
            bond_payload = _network_frame_payload(arrays_file, "bond", source_index)
            if bond_payload:
                frame_payload["bonds"] = bond_payload
            if wall_end > wall_start:
                frame_payload["wallIds"] = _encode_u32(wall_ids[wall_start:wall_end])
                frame_payload["wallVertexIds"] = _encode_u32(
                    wall_vertex_ids[wall_start:wall_end]
                )
                frame_payload["wallXyz"] = _encode_f32(
                    np.asarray(wall_vertex_xyz[wall_start:wall_end], dtype=np.float32)
                )
            chunk_index = viewer_index // CHUNK_FRAMES
            pending_frames.append(frame_payload)
            if len(pending_frames) == CHUNK_FRAMES or viewer_index == len(selected) - 1:
                chunk_path = chunk_dir / f"chunk_{chunk_index:03d}.js"
                chunk_sizes.append(
                    _write_chunk(chunk_path, case_id, chunk_index, pending_frames)
                )
                pending_frames = []

            platen = _series_value(analysis_file, arrays_file, "platen_distance_m", source_index)
            stress_pa = _series_value(
                analysis_file, arrays_file, "axial_stress_pa", source_index
            )
            strain = _series_value(analysis_file, arrays_file, "axial_strain", source_index)
            load_n = _series_value(
                analysis_file, arrays_file, "mean_axial_load_n", source_index
            )
            shortening = (
                float(geometry["height0"]) - platen
                if platen is not None and geometry.get("height0") is not None
                else None
            )
            frames_meta.append(
                {
                    "index": int(viewer_index),
                    "sourceIndex": int(source_index),
                    "chunk": int(chunk_index),
                    "chunkOffset": int(viewer_index % CHUNK_FRAMES),
                    "cycle": int(cycle[source_index]),
                    "time": float(mechanical_time[source_index]),
                    "ballCount": int(len(ids)),
                    "stressPa": stress_pa,
                    "stressMPa": None if stress_pa is None else stress_pa / 1.0e6,
                    "strain": strain,
                    "loadN": load_n,
                    "heightM": platen,
                    "shorteningM": shortening,
                }
            )

        crack_rows, crack_status = _crack_records(
            {key: arrays_file[key] for key in arrays_file.files if key.startswith("fracture_")}
        )
        local_charts = [
            _slice_chart(spec, selected, source_count)
            for spec in chart_specs
            if spec.get("case_id") == case_id
        ]
        charts_text = (
            "window.PFC_VIEWER_DATA.registerCharts("
            + str(case_id)
            + ","
            + _json_text(local_charts)
            + ");\n"
        )
        _write_text(case_data_root / "charts.js", charts_text)

        selected_source = np.asarray(selected, dtype=np.int64)
        viewer_index_by_source = {
            int(source_index): viewer_index
            for viewer_index, source_index in enumerate(selected)
        }
        selected_mask = np.isin(ball_frame_index, selected_source)
        order = np.lexsort((ball_frame_index[selected_mask], ball_ids[selected_mask]))
        ordered_ids = ball_ids[selected_mask][order]
        ordered_rows = np.flatnonzero(selected_mask)[order]
        history_bucket_records: list[list[dict[str, Any]]] = [
            [] for _ in range(HISTORY_BUCKETS)
        ]
        if len(ordered_rows):
            boundaries = np.flatnonzero(np.diff(ordered_ids)) + 1
            groups = np.split(ordered_rows, boundaries)
            for group in groups:
                if not len(group):
                    continue
                ball_id = int(ball_ids[int(group[0])])
                bucket = ball_id % HISTORY_BUCKETS
                history_bucket_records[bucket].append(
                    _history_payload(
                        ball_id=ball_id,
                        source_frame_indices=ball_frame_index[group],
                        viewer_frame_indices=np.asarray(
                            [
                                viewer_index_by_source[int(source_index)]
                                for source_index in ball_frame_index[group]
                            ],
                            dtype=np.int64,
                        ),
                        xyz=ball_xyz[group],
                        displacement=displacement[group],
                        speed=speed[group],
                        acceleration=acceleration[group],
                    )
                )
        history_sizes: list[int] = []
        for bucket, entries in enumerate(history_bucket_records):
            entries.sort(key=lambda item: item["id"])
            path = case_data_root / "histories" / f"bucket_{bucket:03d}.js"
            history_sizes.append(_write_history_bucket(path, case_id, bucket, entries))

        charts = analysis or {}
        frames_text = (
            "window.PFC_VIEWER_DATA.registerCaseMeta("
            + str(case_id)
            + ","
            + _json_text(
                {
                    "id": case_id,
                    "label": case["label"],
                    "runId": case["run_id"],
                    "dimension": int(case["dimension"]),
                    "sourceFrameCount": source_count,
                    "viewerFrameCount": len(selected),
                    "sampled": len(selected) < source_count,
                    "frames": frames_meta,
                    "cracks": crack_rows,
                    "crackStatus": crack_status,
                    "crackEventCount": len(crack_rows),
                    "chunkSize": CHUNK_FRAMES,
                    "chunkCount": len(chunk_sizes),
                    "historyBucketCount": HISTORY_BUCKETS,
                    "historyMetrics": ["displacement", "speed", "acceleration"],
                    "historyFrameStride": 8,
                    "historyFrameFields": [
                        "source_frame_index",
                        "viewer_frame_index",
                        "x",
                        "y",
                        "z",
                        "displacement",
                        "speed",
                        "acceleration",
                    ],
                    "historyForceStatus": "NOT_CAPTURED",
                    "historyStatus": "GENERATED" if history_sizes else "NOT_GENERATED",
                    "entityStatus": entity_status,
                    "metricStatus": metric_status,
                }
            )
            + ");\n"
        )
        _write_text(case_data_root / "meta.js", frames_text)
        if not np.isfinite(lo).all() or not np.isfinite(hi).all():
            lo = np.zeros(3)
            hi = np.ones(3)
        summary = {
            "id": case_id,
            "label": case["label"],
            "runId": case["run_id"],
            "dimension": int(case["dimension"]),
            "sourceFrameCount": source_count,
            "viewerFrameCount": len(selected),
            "frameStatus": "FULL_REAL_FRAME_SET" if len(selected) == source_count else "EXPLICITLY_SAMPLED",
            "ballCountMin": int(case.get("metadata", {}).get("ball_count_min", 0)),
            "ballCountMax": int(case.get("metadata", {}).get("ball_count_max", 0)),
            "fractureEvents": int(case.get("metadata", {}).get("event_count", 0)),
            "crackStatus": crack_status,
            "maxDisplacement": max_displacement,
            "maxSpeed": max_speed,
            "maxAcceleration": max_acceleration,
            "maxContactForce": max_contact_force,
            "bounds": [lo.tolist(), hi.tolist()],
            "chartCount": len(local_charts),
            "metaPath": f"data/cases/case_{case_id}/meta.js",
            "chartsPath": f"data/cases/case_{case_id}/charts.js",
            "chunkPattern": f"data/cases/case_{case_id}/chunks/chunk_{{chunk:03d}}.js",
            "historyPattern": f"data/cases/case_{case_id}/histories/bucket_{{bucket:03d}}.js",
            "chartsStatus": charts.get("status", "NOT_GENERATED"),
            "entityStatus": entity_status,
            "metricStatus": metric_status,
        }
        return (
            summary,
            sum(chunk_sizes),
            sum(history_sizes),
            (case_data_root / "charts.js").stat().st_size
            + (case_data_root / "meta.js").stat().st_size,
        )
    finally:
        arrays_file.close()
        analysis_file.close()


def _analysis_lookup(
    analysis_root: Path,
) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]]]:
    path = analysis_root / "analysis.json"
    if not path.is_file():
        return {}, []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        int(case["case_id"]): case for case in payload.get("cases", [])
    }, list(payload.get("charts", []))


def _directory_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def prepare_payload(
    experiment_root: Path,
    analysis_root: Path,
    data_root: Path,
    *,
    max_frames: int | None = None,
    reuse: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    """Create or reuse a chunked Viewer payload.

    ``max_frames is None`` or ``0`` preserves every captured frame. A positive
    value explicitly samples real frames and is disclosed in the manifest.
    """

    started = time.perf_counter()
    experiment_root = experiment_root.resolve()
    analysis_root = analysis_root.resolve()
    data_root = data_root.resolve()
    experiment = json.loads((experiment_root / "experiment.json").read_text(encoding="utf-8"))
    cases = list(experiment["cases"])
    signature = _source_signature(experiment_root, analysis_root, cases, max_frames)
    signature_sha = hashlib.sha256(_json_text(signature).encode("utf-8")).hexdigest()
    manifest_path = data_root / "payload_manifest.json"
    if reuse and not force and manifest_path.is_file() and (data_root / MARKER).is_file():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("source_signature_sha256") == signature_sha:
            existing["reused"] = True
            existing["elapsed_seconds"] = round(time.perf_counter() - started, 3)
            return existing

    staging = data_root.parent / ".pfc-viewer-payload-staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    _write_text(staging / MARKER, PAYLOAD_VERSION + "\n")
    analyses, chart_specs = _analysis_lookup(analysis_root)

    static = _static_payload(experiment_root, cases)
    _write_text(
        staging / "static.js",
        "window.PFC_VIEWER_DATA.registerStatic(" + _json_text(static) + ");\n",
    )

    summaries: list[dict[str, Any]] = []
    chunk_bytes = 0
    history_bytes = 0
    metadata_bytes = 0
    for case in cases:
        case_id = int(case["case_id"])
        summary, case_chunks, case_histories, case_metadata = _write_case_payload(
            experiment_root,
            analysis_root,
            staging / "cases" / f"case_{case_id}",
            case,
            analyses.get(case_id),
            chart_specs,
            max_frames,
        )
        summaries.append(summary)
        chunk_bytes += case_chunks
        history_bytes += case_histories
        metadata_bytes += case_metadata

    global_charts = [spec for spec in chart_specs if spec.get("case_id") is None]
    if global_charts:
        _write_text(
            staging / "global-charts.js",
            "window.PFC_VIEWER_DATA.registerGlobalCharts("
            + _json_text(global_charts)
            + ");\n",
        )

    lo = np.asarray([math.inf, math.inf, math.inf])
    hi = np.asarray([-math.inf, -math.inf, -math.inf])
    for ball in static["balls"]:
        radius = max(float(ball[4]), 0.0)
        lo = np.minimum(lo, np.asarray(ball[1:4]) - radius)
        hi = np.maximum(hi, np.asarray(ball[1:4]) + radius)
    for wall in static["walls"]:
        for vertex in wall["vertices"]:
            lo = np.minimum(lo, np.asarray(vertex["position"]))
            hi = np.maximum(hi, np.asarray(vertex["position"]))
    for summary in summaries:
        lo = np.minimum(lo, np.asarray(summary["bounds"][0]))
        hi = np.maximum(hi, np.asarray(summary["bounds"][1]))
    for axis in range(3):
        pad = 0.025 * max(float(hi[axis] - lo[axis]), 1.0e-9)
        lo[axis] -= pad
        hi[axis] += pad

    default_case = max(
        summaries,
        key=lambda item: (int(item["fractureEvents"]), int(item["viewerFrameCount"]), int(item["id"])),
    )["id"]
    catalog = {
        "meta": {
            "schemaVersion": experiment["schema_version"],
            "payloadVersion": PAYLOAD_VERSION,
            "title": experiment["title"],
            "dataBoundary": experiment.get("data_boundary", "UNKNOWN"),
            "dimension": 2 if all(int(case["dimension"]) == 2 for case in cases) else 3,
            "defaultCase": int(default_case),
            "domain": {"min": lo.tolist(), "max": hi.tolist()},
            "colors": {
                "primary": "#3C5488",
                "fracture": "#E64B35",
                "slate": "#8491B4",
                "tan": "#B09C85",
                "accent": "#F39B7F",
                "low": "#EAEEF5",
                "high": "#3C5488",
                "missing": "#A8ADB7",
            },
            "chunkFrames": CHUNK_FRAMES,
            "historyBuckets": HISTORY_BUCKETS,
            "globalChartsPath": "data/global-charts.js" if global_charts else None,
            "visualCapabilities": {
                "entities": {
                    key: (
                        "SUPPORTED"
                        if any(
                            summary["entityStatus"].get(key) == "SUPPORTED"
                            for summary in summaries
                        )
                        else "NOT_CAPTURED"
                    )
                    for key in ("ball", "wall", "fracture", "contact", "bond", "clump")
                },
                "particleMetrics": {
                    key: (
                        "SUPPORTED"
                        if any(
                            summary["metricStatus"].get(key) == "SUPPORTED"
                            for summary in summaries
                        )
                        else "NOT_CAPTURED"
                    )
                    for key in ("displacement", "speed", "acceleration", "contactForce")
                },
            },
        },
        "cases": summaries,
    }
    _write_text(
        staging / "catalog.js",
        "window.PFC_VIEWER_DATA.registerCatalog(" + _json_text(catalog) + ");\n",
    )

    manifest = {
        "status": "GENERATED",
        "verification_status": "NOT_VERIFIED",
        "payload_version": PAYLOAD_VERSION,
        "reused": False,
        "source_signature_sha256": signature_sha,
        "frame_policy": (
            "ALL_REAL_FRAMES"
            if not max_frames
            else f"EXPLICITLY_SAMPLED_AT_MOST_{max_frames}_REAL_FRAMES"
        ),
        "chunk_frames": CHUNK_FRAMES,
        "history_buckets": HISTORY_BUCKETS,
        "case_count": len(summaries),
        "cases": summaries,
        "sizes": {
            "catalog_bytes": (staging / "catalog.js").stat().st_size,
            "static_bytes": (staging / "static.js").stat().st_size,
            "chunk_bytes": chunk_bytes,
            "history_bytes": history_bytes,
            "metadata_and_chart_bytes": metadata_bytes,
        },
    }
    manifest["sizes"]["total_bytes"] = _directory_bytes(staging)
    _write_json(staging / "payload_manifest.json", manifest)

    if data_root.exists():
        if not (data_root / MARKER).is_file():
            raise PayloadBuildError(
                f"Refusing to replace non-generated payload directory: {data_root}"
            )
        shutil.rmtree(data_root)
    staging.replace(data_root)
    manifest["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    return manifest

