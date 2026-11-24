"""Build a MOCK standardized experiment that exercises the PFC-SV kernel.

This script is a DATA-ONLY generator. It writes a new immutable
``pfc.standardized-experiment@1.0.0`` package under examples/ with:

* 8,432 PFC3D Ball observations per frame across 21 real frames;
* declared MOCK extension channels for per-Ball contact force, orientation
  and local strain, so the kernel can derive the reference-image charts
  through its normal formula/channel-decision path;
* correct delivery_manifest.json hashes so standard_contract.verify accepts it.

All values are synthetic and labeled ``MOCK`` / ``DECLARED_MOCK``. Nothing here
is a real PFC solve. A fixed seed makes the package reproducible (spec 2.1).
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np

SEED = 20261121
FRAMES = 21
BALLS = 8432
DIM = 3
HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "standardized_data" / "Mock_Experiment"
OUTPUT = HERE / "standardized_data" / "Mock_Showcase"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def channel_record(channel_id, entity, variable, unit, source, status, dims, desc):
    return {
        "schema_version": "1.0.0",
        "id": channel_id,
        "entity_type": entity,
        "variable": variable,
        "unit": unit,
        "source": source,
        "status": status,
        "dimensions": dims,
        "description": desc,
        "provenance": {
            "source": source,
            "input_files": [],
            "parent_results": [],
            "formula": None,
            "method": "MOCK showcase synthetic capture",
            "applicability": "MOCK / DEMO only",
            "notes": ["Synthetic values; not a real PFC solve."],
            "generated_utc": "2026-11-21T00:00:00+00:00",
        },
    }


def main() -> int:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    (OUTPUT / "cases" / "case_0").mkdir(parents=True)
    (OUTPUT / "schema").mkdir()

    rng = np.random.default_rng(SEED)

    # ---- frame scalars ---------------------------------------------------
    cycle = np.arange(FRAMES, dtype=np.int64) * 1250
    cycle[0] = 1
    time = np.linspace(0.0, 0.25, FRAMES, dtype=np.float64)
    strain = np.linspace(0.0, 0.02, FRAMES, dtype=np.float64)
    # monotonic-then-softening nominal stress in Pa, peak ~78.5 MPa
    stress_pa = 78.5e6 * np.sin(np.pi * np.linspace(0.02, 0.62, FRAMES)) ** 0.7
    top_force = stress_pa * 4.0
    bottom_force = stress_pa * 4.0
    platen = 2.4 * (1.0 - strain)

    # ---- ball entities, variable-length offsets --------------------------
    frame_offsets = np.zeros(FRAMES + 1, dtype=np.int64)
    ids_list, xyz_list, radius_list, frame_index_list = [], [], [], []
    force_list, orient_list, strain_list = [], [], []
    ball_id = 1
    grid_n = int(np.ceil(BALLS ** (1 / 3)))  # ~21
    for f in range(FRAMES):
        compression = strain[f]
        for i in range(BALLS):
            gx, gy, gz = i % grid_n, (i // grid_n) % grid_n, i // (grid_n * grid_n)
            spacing = 2.0 / (grid_n - 1)
            x = -1 + gx * spacing + rng.normal(0, 0.006)
            y = -1 + gy * spacing + rng.normal(0, 0.006)
            z = -1 + gz * spacing * (1 - compression) + rng.normal(0, 0.006)
            r = 0.026 + rng.gamma(2.0, 0.005)
            shear_band = np.exp(-((x / 0.32) ** 2))
            force = float(10 ** (rng.uniform(0, 0.45) + 2.6 * shear_band))
            orientation = float((np.degrees(np.arctan2(y, x)) + 360 * rng.random()) % 180)
            local_strain = float(compression * (0.6 + 1.4 * shear_band) + rng.normal(0, 0.0004))
            ids_list.append(ball_id); ball_id += 1
            xyz_list.append((x, y, z))
            radius_list.append(r)
            frame_index_list.append(f)
            force_list.append(force)
            orient_list.append(orientation)
            strain_list.append(local_strain)
        frame_offsets[f + 1] = len(ids_list)

    ball_id_arr = np.asarray(ids_list, dtype=np.uint64)
    ball_xyz = np.asarray(xyz_list, dtype=np.float64)
    ball_radius = np.asarray(radius_list, dtype=np.float64)
    ball_frame_index = np.asarray(frame_index_list, dtype=np.int64)

    # ---- walls: a box, one quad per wall replicated per frame ------------
    wall_offsets = np.zeros(FRAMES + 1, dtype=np.int64)
    w_ids, w_vids, w_xyz = [], [], []
    wid = 1
    corners = np.array([
        [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
        [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1],
    ], dtype=np.float64)
    for f in range(FRAMES):
        for base in corners:
            p = base.copy(); p[2] *= (1 - strain[f])
            w_ids.append(wid); w_vids.append(wid); w_xyz.append(p); wid += 1
        wall_offsets[f + 1] = len(w_ids)

    # ---- fracture events -------------------------------------------------
    n_events = 12
    ev_cycle = np.sort(rng.choice(cycle[3:], n_events, replace=True))
    ev_time = np.interp(ev_cycle, cycle, time)
    ev_mode = np.where(rng.random(n_events) > 0.5, 1, 2).astype(np.int8)
    ev_pos = rng.uniform(-0.9, 0.9, (n_events, 3))
    ev_normal = rng.normal(size=(n_events, 3))
    ev_normal /= np.linalg.norm(ev_normal, axis=1, keepdims=True)
    ev_diam = rng.uniform(0.02, 0.08, n_events)

    arrays = {
        "cycle": cycle,
        "mechanical_time_total": time,
        "frame_offsets": frame_offsets,
        "ball_id": ball_id_arr,
        "ball_xyz": ball_xyz,
        "ball_radius": ball_radius,
        "ball_frame_index": ball_frame_index,
        "wall_offsets": wall_offsets,
        "wall_id": np.asarray(w_ids, dtype=np.uint64),
        "wall_vertex_id": np.asarray(w_vids, dtype=np.uint64),
        "wall_vertex_xyz": np.asarray(w_xyz, dtype=np.float64),
        "fracture_event_id": np.arange(1, n_events + 1, dtype=np.int64),
        "fracture_cycle": ev_cycle,
        "fracture_mechanical_time_total": ev_time,
        "fracture_mode": ev_mode,
        "fracture_position": ev_pos,
        "fracture_normal": ev_normal,
        "fracture_diameter": ev_diam,
        "top_force_n": top_force,
        "bottom_force_n": bottom_force,
        "platen_distance_m": platen,
        "axial_strain": strain,
        "axial_stress_pa": stress_pa,
        # MOCK extension channels, explicitly declared below
        "ball_contact_force_n": np.asarray(force_list, dtype=np.float64),
        "ball_orientation_deg": np.asarray(orient_list, dtype=np.float64),
        "ball_strain_local": np.asarray(strain_list, dtype=np.float64),
    }
    npz_path = OUTPUT / "cases" / "case_0" / "arrays.npz"
    np.savez_compressed(npz_path, **arrays)

    # ---- sidecars --------------------------------------------------------
    base_channels = [
        channel_record("cycle", "history", "cycle", "cycle", "MOCK", "GENERATED", ["frame"], "MOCK frame Cycle."),
        channel_record("mechanical_time_total", "history", "mechanical_time_total", "s", "MOCK", "GENERATED", ["frame"], "MOCK mechanical time."),
        channel_record("ball_id", "ball", "id", None, "MOCK", "GENERATED", ["entity", "frame_variable_length"], "Stable MOCK Ball ID."),
        channel_record("ball_xyz", "ball", "position", "m", "MOCK", "GENERATED", ["entity", "xyz"], "MOCK Ball coordinates."),
        channel_record("ball_radius", "ball", "radius", "m", "MOCK", "GENERATED", ["entity"], "Synthetic particle size."),
        channel_record("ball_contact_force_n", "ball", "contact_force_magnitude", "N", "DECLARED_MOCK", "GENERATED", ["entity"], "MOCK per-Ball contact force magnitude."),
        channel_record("ball_orientation_deg", "ball", "orientation", "degree", "DECLARED_MOCK", "GENERATED", ["entity"], "MOCK per-Ball orientation angle."),
        channel_record("ball_strain_local", "ball", "local_strain", "1", "DECLARED_MOCK", "GENERATED", ["entity"], "MOCK per-Ball local axial strain."),
        channel_record("axial_strain", "sample", "axial_strain", "1", "DECLARED_MOCK", "GENERATED", ["frame"], "MOCK nominal axial strain."),
        channel_record("axial_stress_pa", "sample", "axial_stress", "Pa", "DECLARED_MOCK", "GENERATED", ["frame"], "MOCK nominal axial stress."),
        channel_record("fracture_event", "fracture", "bond_break", "event", "MOCK", "GENERATED", ["event"], "MOCK fracture events."),
        channel_record("fracture_normal", "fracture", "normal", None, "MOCK", "GENERATED", ["event", "xyz"], "MOCK fracture normals."),
        channel_record("top_force_n", "wall", "contact_force_magnitude", "N", "MOCK", "GENERATED", ["frame"], "MOCK platen force."),
        channel_record("bottom_force_n", "wall", "contact_force_magnitude", "N", "MOCK", "GENERATED", ["frame"], "MOCK platen force."),
    ]
    dump(OUTPUT / "cases" / "case_0" / "channels.json", base_channels)

    frames = []
    for f in range(FRAMES):
        frames.append({
            "frame_id": f, "cycle": int(cycle[f]),
            "mechanical_time_total": float(time[f]),
            "ball_offset": int(frame_offsets[f]), "ball_count": BALLS,
            "wall_offset": int(wall_offsets[f]), "wall_vertex_count": 8,
        })
    dump(OUTPUT / "cases" / "case_0" / "frames.json", frames)

    events = []
    for i in range(n_events):
        events.append({
            "event_id": int(i + 1), "cycle": int(ev_cycle[i]),
            "mechanical_time_total": float(ev_time[i]), "mode": int(ev_mode[i]),
            "position": [float(v) for v in ev_pos[i]],
            "normal": [float(v) for v in ev_normal[i]],
            "diameter": float(ev_diam[i]),
        })
    dump(OUTPUT / "cases" / "case_0" / "events.json", events)

    case = {
        "schema_version": "1.0.0",
        "case_id": 0,
        "label": "PFC-SV MOCK Showcase",
        "run_id": "mock_showcase_run",
        "dimension": DIM,
        "source_format": "mock-showcase-generator",
        "frame_count": FRAMES,
        "arrays_path": "cases/case_0/arrays.npz",
        "channels": base_channels,
        "entity_groups": [
            {"entity_type": "ball", "array_prefix": "ball", "count": BALLS,
             "dynamic_ids": False,
             "properties": ["id", "position", "radius", "frame_index",
                            "contact_force_n", "orientation_deg", "local_strain"],
             "source": "MOCK"},
            {"entity_type": "wall", "array_prefix": "wall", "count": 8,
             "dynamic_ids": False, "properties": ["id", "vertex_position"], "source": "MOCK"},
            {"entity_type": "fracture", "array_prefix": "fracture", "count": n_events,
             "dynamic_ids": False,
             "properties": ["id", "cycle", "position", "normal", "mode", "diameter"],
             "source": "MOCK"},
        ],
        "metadata": {
            "geometry": {
                "dimension": DIM, "axis": "z", "axis_index": 2,
                "top": 10, "bottom": 20, "height0": 2.0, "area0": 4.0,
                "area_kind": "cross_section_area",
                "transverse_spans": [{"axis": "x", "extent": 2.0}, {"axis": "y", "extent": 2.0}],
            },
            "ball_count_min": BALLS, "ball_count_max": BALLS,
            "event_count": n_events, "mechanical_time_start": 0.0,
            "mechanical_time_end": 0.25,
        },
        "provenance": {
            "source": "MOCK", "input_files": [], "parent_results": [],
            "formula": None, "method": "mock-showcase-generator",
            "applicability": "MOCK / DEMO only",
            "notes": ["All values are synthetic and labeled MOCK."],
            "generated_utc": "2026-11-21T00:00:00+00:00",
        },
    }
    dump(OUTPUT / "cases" / "case_0" / "case.json", case)

    dump(OUTPUT / "cases" / "case_0" / "entity_changes.json", {
        "status": "GENERATED", "policy": "constant ID set in MOCK showcase",
        "frames": [], "added_id_count": 0, "removed_id_count": 0,
    })

    static = {
        "dimension": DIM,
        "balls": [
            {"id": int(ball_id_arr[i]), "x": float(ball_xyz[i, 0]),
             "y": float(ball_xyz[i, 1]), "z": float(ball_xyz[i, 2]),
             "radius": float(ball_radius[i])}
            for i in range(BALLS)
        ],
        "walls": [{
            "id": 10, "name": "box", "position": [0.0, 0.0, 0.0],
            "vertices": [
                {"id": vi + 1, "position": [float(v) for v in c]}
                for vi, c in enumerate(corners)
            ],
        }],
        "geometry": {"dimension": DIM, "axis": "z", "axis_index": 2,
                     "top": 10, "bottom": 20, "height0": 2.0, "area0": 4.0,
                     "area_kind": "cross_section_area",
                     "transverse_spans": [{"axis": "x", "extent": 2.0},
                                          {"axis": "y", "extent": 2.0}]},
    }
    dump(OUTPUT / "cases" / "case_0" / "static.json", static)

    with (OUTPUT / "cases" / "case_0" / "frame_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["frame_id", "cycle", "mechanical_time", "ball_count", "axial_strain", "axial_stress_pa"])
        for f in range(FRAMES):
            writer.writerow([f, int(cycle[f]), f"{time[f]:.6f}", BALLS, f"{strain[f]:.6f}", f"{stress_pa[f]:.3f}"])

    dump(OUTPUT / "cases" / "case_0" / "conversion_report.json", {
        "status": "GENERATED", "case_id": 0, "input_files": [],
        "output_file": "cases/case_0/arrays.npz", "output_sha256": sha256(npz_path),
        "arrays": {k: list(v.shape) for k, v in arrays.items()},
        "integrity": {"frame_offsets_consistent": True, "finite_coordinates": True},
        "entity_changes": {"status": "GENERATED"},
        "missing_fields": [], "truth_boundary": "MOCK / DEMO only; not a real PFC solve.",
    })

    experiment = {
        "schema_version": "1.0.0",
        "experiment_id": "Mock_Showcase",
        "title": "PFC-SV MOCK Showcase",
        "pfc_version": None,
        "execution_mode": "OFFLINE",
        "dimensions": [DIM],
        "data_boundary": "MOCK",
        "cases": [case],
        "metadata": {
            "conversion": "NumPy NPZ with variable-length entity offsets",
            "raw_input_root": "GENERATED", "case_count": 1,
            "extension_channels": ["ball.contact_force", "ball.orientation", "ball.local_strain"],
        },
        "provenance": {
            "source": "MOCK", "input_files": [], "parent_results": [],
            "formula": None, "method": "mock-showcase-generator",
            "applicability": "MOCK / DEMO only",
            "notes": ["Synthetic values reproducing a reference layout; not experimental results."],
            "generated_utc": "2026-11-21T00:00:00+00:00",
        },
        "generated_utc": "2026-11-21T00:00:00+00:00",
    }
    dump(OUTPUT / "experiment.json", experiment)
    dump(OUTPUT / "conversion_report.json", {
        "status": "GENERATED", "experiment_id": "Mock_Showcase",
        "case_count": 1, "data_boundary": "MOCK",
        "truth_boundary": "MOCK / DEMO only.",
    })

    # copy schemas from template
    for schema in (TEMPLATE / "schema").glob("*.json"):
        shutil.copy2(schema, OUTPUT / "schema" / schema.name)

    # ---- delivery manifest with correct hashes --------------------------
    artifacts = []
    for path in sorted(OUTPUT.rglob("*")):
        if path.is_file() and path.name != "delivery_manifest.json":
            artifacts.append({
                "path": path.relative_to(OUTPUT).as_posix(),
                "sha256": sha256(path), "size_bytes": path.stat().st_size,
            })
    manifest = {
        "contract": {
            "name": "pfc.standardized-experiment", "version": "1.0.0",
            "schema_version": "1.0.0", "immutable": True,
            "scope": "STANDARDIZED_EXPERIMENT_DATA",
        },
        "producer": {"skill": "pfc-scientific-visualization", "entrypoint": "build_mock_showcase"},
        "experiment": {
            "path": "experiment.json",
            "sha256": sha256(OUTPUT / "experiment.json"),
            "size_bytes": (OUTPUT / "experiment.json").stat().st_size,
        },
        "raw_input": {"root": "GENERATED", "read_only": True,
                      "embedded_in_contract": False, "input_file_count": 0},
        "consumer_policy": {"read_only": True, "may_write_inside_contract": False},
        "cases": [{
            "case_id": 0,
            "conversion_report": "cases/case_0/conversion_report.json",
            "arrays": "cases/case_0/arrays.npz",
            "arrays_sha256": sha256(npz_path),
        }],
        "artifacts": artifacts,
    }
    dump(OUTPUT / "delivery_manifest.json", manifest)

    print(f"Built MOCK package: {OUTPUT}")
    print(f"  frames={FRAMES} balls/frame={BALLS} total_ball_rows={len(ball_id_arr)}")
    print(f"  extension channels: contact_force, orientation, local_strain")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
