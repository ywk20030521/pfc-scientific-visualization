"""Build a MOCK standardized experiment that exercises EVERY Viewer channel.

This is a DATA-ONLY test generator.  It writes a new immutable
``pfc.standardized-experiment@1.0.0`` package under examples/standardized_data/
that deliberately declares all optional entities as SUPPORTED so the full
Viewer capability can be regression-tested:

* ball positions/radii moving every frame;
* real wall FACE geometry: each wall is a 4-corner quad replicated per frame,
  so the Viewer can render solid wall plates (not a Z polyline);
* fracture events WITH endpoint Ball IDs -> dynamic cracks that follow balls;
* contact network (contact_ball_id_a/b + force) per frame;
* bond network (bond_ball_id_a/b + force) per frame;
* per-ball contact-force scalar for the color ramp.

All values are synthetic and labeled MOCK.  Nothing here is a real PFC solve.
A fixed seed makes the package reproducible.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np

SEED = 20261123
FRAMES = 24
BALLS = 240
DIM = 3
HERE = Path(__file__).resolve().parent
STD_ROOT = HERE / "standardized_data"
TEMPLATE = STD_ROOT / "Mock_Experiment"
OUTPUT = STD_ROOT / "FullCapability_Mock"


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
            "method": "MOCK full-capability synthetic capture",
            "applicability": "MOCK / DEMO only",
            "notes": ["Synthetic values; not a real PFC solve."],
            "generated_utc": "2026-11-23T00:00:00+00:00",
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
    cycle = np.arange(FRAMES, dtype=np.int64) * 500 + 1
    time = np.linspace(0.0, 0.30, FRAMES, dtype=np.float64)
    strain = np.linspace(0.0, 0.03, FRAMES, dtype=np.float64)
    stress_pa = 60.0e6 * np.sin(np.pi * np.linspace(0.02, 0.85, FRAMES)) ** 0.7
    platen = 2.0 * (1.0 - strain)

    # ---- balls: fixed ID set, positions move every frame ----------------
    frame_offsets = np.zeros(FRAMES + 1, dtype=np.int64)
    ids_list, xyz_list, radius_list, frame_index_list = [], [], [], []
    force_list = []
    grid_n = int(np.ceil(BALLS ** (1 / 3)))
    spacing = 1.9 / (grid_n - 1)
    base_xy = []
    for i in range(BALLS):
        gx, gy, gz = i % grid_n, (i // grid_n) % grid_n, i // (grid_n * grid_n)
        base_xy.append((-0.95 + gx * spacing, -0.95 + gy * spacing, gz))
    for f in range(FRAMES):
        compression = strain[f]
        for i in range(BALLS):
            bx, by, bz = base_xy[i]
            x = bx + 0.04 * np.sin(2.0 * np.pi * f / FRAMES + i * 0.13)
            y = by + 0.04 * np.cos(2.0 * np.pi * f / FRAMES + i * 0.11)
            z = -0.95 + bz * spacing * (1 - compression) + rng.normal(0, 0.004)
            r = 0.030 + rng.gamma(2.0, 0.004)
            shear_band = np.exp(-((x / 0.35) ** 2))
            force = float(10 ** (rng.uniform(0, 0.4) + 2.6 * shear_band))
            ids_list.append(i + 1)
            xyz_list.append((x, y, z))
            radius_list.append(r)
            frame_index_list.append(f)
            force_list.append(force)
        frame_offsets[f + 1] = len(ids_list)

    ball_id_arr = np.asarray(ids_list, dtype=np.uint64)
    ball_xyz = np.asarray(xyz_list, dtype=np.float64)
    ball_radius = np.asarray(radius_list, dtype=np.float64)
    ball_frame_index = np.asarray(frame_index_list, dtype=np.int64)
    ball_force = np.asarray(force_list, dtype=np.float64)

    # ---- walls: two solid plates (top/bottom), 4 corner ring per frame ----
    # updateWalls() links consecutive vertexIds within the same wallId; giving
    # each plate four ordered corners yields a real rectangular plate outline
    # that the Viewer extrudes into a solid instanced bar per edge.
    wall_offsets = np.zeros(FRAMES + 1, dtype=np.int64)
    w_ids, w_vids, w_xyz = [], [], []
    plate_z = {101: -1.0, 102: 1.0}
    for f in range(FRAMES):
        for wid, zbase in plate_z.items():
            z = zbase * (1 - strain[f])
            ring = [(-1.05, -1.05, z), (1.05, -1.05, z),
                    (1.05, 1.05, z), (-1.05, 1.05, z)]
            for vi, corner in enumerate(ring):
                w_ids.append(wid)
                w_vids.append(vi + 1)
                w_xyz.append(corner)
        wall_offsets[f + 1] = len(w_ids)

    # ---- fracture events WITH endpoint ball IDs (dynamic cracks) --------
    # Endpoints are two adjacent balls whose bond breaks; the Viewer re-anchors
    # the crack midpoint to these balls' CURRENT positions each frame.
    n_events = 40
    ev_cycle = np.sort(rng.choice(cycle[3:], n_events, replace=True))
    ev_time = np.interp(ev_cycle, cycle, time)
    ev_mode = np.where(rng.random(n_events) > 0.5, 1, 2).astype(np.int8)
    ev_ball_a = rng.integers(1, BALLS - grid_n, n_events, dtype=np.int64)
    ev_ball_b = ev_ball_a + grid_n  # vertical neighbour
    ev_pos = []
    ev_normal = []
    ev_diam = []
    for i in range(n_events):
        ia = int(ev_ball_a[i]) - 1
        ib = int(ev_ball_b[i]) - 1
        # break event happens near the end of the ramp; use a representative
        # mid-run frame position for the captured break midpoint.
        f = max(0, min(FRAMES - 1, int(np.searchsorted(cycle, ev_cycle[i]))))
        pa = ball_xyz[f * BALLS + ia]
        pb = ball_xyz[f * BALLS + ib]
        ev_pos.append((pa + pb) / 2.0)
        normal = pb - pa
        norm = np.linalg.norm(normal)
        normal = normal / norm if norm > 1e-9 else np.array([0.0, 0.0, 1.0])
        ev_normal.append(normal)
        ev_diam.append(float(np.linalg.norm(pb - pa)))
    ev_pos = np.asarray(ev_pos)
    ev_normal = np.asarray(ev_normal)
    ev_diam = np.asarray(ev_diam)

    # ---- contact network per frame --------------------------------------
    # Uses the REAL headless converter field names so this test exercises the
    # exact contract shipped by pfc-headless (not an invented spelling):
    #   contact_offsets / contact_end1_id / contact_end2_id / contact_force_xyz
    contact_offsets = np.zeros(FRAMES + 1, dtype=np.int64)
    c_a, c_b, c_force_xyz, c_xyz, c_id = [], [], [], [], []
    next_contact_id = 1
    for f in range(FRAMES):
        pairs = _neighbour_pairs(BALLS, grid_n, rng)
        for a, b in pairs:
            c_id.append(next_contact_id); next_contact_id += 1
            c_a.append(a)
            c_b.append(b)
            ia, ib = a - 1, b - 1
            mid = (ball_xyz[f * BALLS + ia] + ball_xyz[f * BALLS + ib]) / 2.0
            c_xyz.append(mid)
            mag = float(rng.uniform(1.0, 40.0))
            c_force_xyz.append([mag / np.sqrt(3), mag / np.sqrt(3), mag / np.sqrt(3)])
        contact_offsets[f + 1] = len(c_a)

    # ---- bond network per frame ------------------------------------------
    # EXTENSION CHANNEL: headless does not yet emit a standalone bond array
    # (bond breaks are recorded only as fracture events).  Kept here to test
    # the Viewer's bond rendering capability; labeled MOCK extension.
    bond_offsets = np.zeros(FRAMES + 1, dtype=np.int64)
    b_a, b_b, b_force = [], [], []
    for f in range(FRAMES):
        pairs = _neighbour_pairs(BALLS, grid_n, rng)
        for a, b in pairs:
            b_a.append(a)
            b_b.append(b)
            b_force.append(float(rng.uniform(5.0, 80.0)))
        bond_offsets[f + 1] = len(b_a)

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
        # EXTENSION (dynamic cracks): headless fracture events do not carry
        # endpoint Ball IDs; added here only to test the Viewer's dynamic-crack
        # path.  Real captures stay static via fracture_position.
        "fracture_ball_id_a": ev_ball_a,
        "fracture_ball_id_b": ev_ball_b,
        # REAL headless contact contract fields:
        "contact_offsets": contact_offsets,
        "contact_id": np.asarray(c_id, dtype=np.uint64),
        "contact_xyz": np.asarray(c_xyz, dtype=np.float64).reshape((-1, 3)),
        "contact_force_xyz": np.asarray(c_force_xyz, dtype=np.float64).reshape((-1, 3)),
        "contact_end1_id": np.asarray(c_a, dtype=np.uint64),
        "contact_end2_id": np.asarray(c_b, dtype=np.uint64),
        # EXTENSION bond channel (MOCK): tests Viewer bond rendering only.
        "bond_frame_offsets": bond_offsets,
        "bond_ball_id_a": np.asarray(b_a, dtype=np.uint64),
        "bond_ball_id_b": np.asarray(b_b, dtype=np.uint64),
        "bond_force_n": np.asarray(b_force, dtype=np.float64),
        "top_force_n": stress_pa * 4.0,
        "bottom_force_n": stress_pa * 4.0,
        "platen_distance_m": platen,
        "axial_strain": strain,
        "axial_stress_pa": stress_pa,
        "ball_contact_force_n": ball_force,
    }
    npz_path = OUTPUT / "cases" / "case_0" / "arrays.npz"
    np.savez_compressed(npz_path, **arrays)

    # ---- channels / sidecars --------------------------------------------
    channels = [
        channel_record("cycle", "history", "cycle", "cycle", "MOCK", "GENERATED", ["frame"], "MOCK frame Cycle."),
        channel_record("mechanical_time_total", "history", "mechanical_time_total", "s", "MOCK", "GENERATED", ["frame"], "MOCK mechanical time."),
        channel_record("ball_id", "ball", "id", None, "MOCK", "GENERATED", ["entity", "frame_variable_length"], "Stable MOCK Ball ID."),
        channel_record("ball_xyz", "ball", "position", "m", "MOCK", "GENERATED", ["entity", "xyz"], "MOCK Ball coordinates."),
        channel_record("ball_radius", "ball", "radius", "m", "MOCK", "GENERATED", ["entity"], "Synthetic particle size."),
        channel_record("ball_contact_force_n", "ball", "contact_force_magnitude", "N", "DECLARED_MOCK", "GENERATED", ["entity"], "MOCK per-Ball contact force."),
        channel_record("wall_position", "wall", "vertex_position", "m", "MOCK", "GENERATED", ["entity", "xyz"], "MOCK solid wall plate corners."),
        channel_record("fracture_event", "fracture", "bond_break", "event", "MOCK", "GENERATED", ["event"], "MOCK fracture events with endpoint Ball IDs."),
        channel_record("contact_network", "contact", "endpoint_ids", None, "MOCK", "GENERATED", ["frame", "contact"], "MOCK contact endpoints."),
        channel_record("contact_force", "contact", "force_magnitude", "N", "MOCK", "GENERATED", ["frame", "contact"], "MOCK contact force."),
        channel_record("bond_network", "bond", "endpoint_ids", None, "MOCK", "GENERATED", ["frame", "bond"], "MOCK bond endpoints."),
        channel_record("bond_force", "bond", "force_magnitude", "N", "MOCK", "GENERATED", ["frame", "bond"], "MOCK bond force."),
        channel_record("axial_strain", "sample", "axial_strain", "1", "DECLARED_MOCK", "GENERATED", ["frame"], "MOCK nominal axial strain."),
        channel_record("axial_stress_pa", "sample", "axial_stress", "Pa", "DECLARED_MOCK", "GENERATED", ["frame"], "MOCK nominal axial stress."),
    ]
    dump(OUTPUT / "cases" / "case_0" / "channels.json", channels)

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
            "ball_id_a": int(ev_ball_a[i]), "ball_id_b": int(ev_ball_b[i]),
        })
    dump(OUTPUT / "cases" / "case_0" / "events.json", events)

    case = {
        "schema_version": "1.0.0",
        "case_id": 0,
        "label": "PFC-SV MOCK Full-Capability",
        "run_id": "mock_fullcap_run",
        "dimension": DIM,
        "source_format": "mock-fullcap-generator",
        "frame_count": FRAMES,
        "arrays_path": "cases/case_0/arrays.npz",
        "channels": channels,
        "entity_groups": [
            {"entity_type": "ball", "array_prefix": "ball", "count": BALLS,
             "dynamic_ids": False, "properties": ["id", "position", "radius", "frame_index", "contact_force_n"], "source": "MOCK"},
            {"entity_type": "wall", "array_prefix": "wall", "count": 8,
             "dynamic_ids": False, "properties": ["id", "vertex_position"], "source": "MOCK"},
            {"entity_type": "fracture", "array_prefix": "fracture", "count": n_events,
             "dynamic_ids": False, "properties": ["id", "cycle", "position", "normal", "mode", "diameter", "ball_id_a", "ball_id_b"], "source": "MOCK"},
            {"entity_type": "contact", "array_prefix": "contact", "dynamic_ids": True, "source": "MOCK"},
            {"entity_type": "bond", "array_prefix": "bond", "dynamic_ids": True, "source": "MOCK"},
        ],
        "metadata": {
            "geometry": {"dimension": DIM, "axis": "z", "axis_index": 2,
                         "top": 101, "bottom": 102, "height0": 2.0, "area0": 4.0,
                         "area_kind": "cross_section_area",
                         "transverse_spans": [{"axis": "x", "extent": 2.0}, {"axis": "y", "extent": 2.0}]},
            "ball_count_min": BALLS, "ball_count_max": BALLS,
            "event_count": n_events, "mechanical_time_start": 0.0, "mechanical_time_end": 0.30,
        },
        "provenance": {
            "source": "MOCK", "input_files": [], "parent_results": [],
            "formula": None, "method": "mock-fullcap-generator",
            "applicability": "MOCK / DEMO only",
            "notes": ["All values are synthetic and labeled MOCK."],
            "generated_utc": "2026-11-23T00:00:00+00:00",
        },
    }
    dump(OUTPUT / "cases" / "case_0" / "case.json", case)

    dump(OUTPUT / "cases" / "case_0" / "entity_changes.json", {
        "status": "GENERATED", "policy": "constant ID set in MOCK full-capability",
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
        "walls": [
            {"id": 101, "name": "bottom plate", "position": [0.0, 0.0, -1.0],
             "vertices": [{"id": vi + 1, "position": [float(v) for v in c]}
                          for vi, c in enumerate([(-1.05, -1.05, -1.0), (1.05, -1.05, -1.0),
                                                  (1.05, 1.05, -1.0), (-1.05, 1.05, -1.0)])]},
            {"id": 102, "name": "top plate", "position": [0.0, 0.0, 1.0],
             "vertices": [{"id": vi + 1, "position": [float(v) for v in c]}
                          for vi, c in enumerate([(-1.05, -1.05, 1.0), (1.05, -1.05, 1.0),
                                                  (1.05, 1.05, 1.0), (-1.05, 1.05, 1.0)])]},
        ],
        "geometry": {"dimension": DIM, "axis": "z", "axis_index": 2,
                     "top": 101, "bottom": 102, "height0": 2.0, "area0": 4.0,
                     "area_kind": "cross_section_area",
                     "transverse_spans": [{"axis": "x", "extent": 2.0}, {"axis": "y", "extent": 2.0}]},
    }
    dump(OUTPUT / "cases" / "case_0" / "static.json", static)

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
        "experiment_id": "FullCapability_Mock",
        "title": "PFC-SV MOCK Full-Capability",
        "pfc_version": None,
        "execution_mode": "OFFLINE",
        "dimensions": [DIM],
        "data_boundary": "MOCK",
        "cases": [case],
        "metadata": {
            "conversion": "NumPy NPZ with variable-length entity offsets",
            "raw_input_root": "GENERATED", "case_count": 1,
            "extension_channels": ["ball.contact_force", "contact.network", "contact.force", "bond.network", "bond.force"],
        },
        "provenance": {
            "source": "MOCK", "input_files": [], "parent_results": [],
            "formula": None, "method": "mock-fullcap-generator",
            "applicability": "MOCK / DEMO only",
            "notes": ["Synthetic values exercising all Viewer channels; not experimental results."],
            "generated_utc": "2026-11-23T00:00:00+00:00",
        },
        "generated_utc": "2026-11-23T00:00:00+00:00",
    }
    dump(OUTPUT / "experiment.json", experiment)
    dump(OUTPUT / "conversion_report.json", {
        "status": "GENERATED", "experiment_id": "FullCapability_Mock",
        "case_count": 1, "data_boundary": "MOCK",
        "truth_boundary": "MOCK / DEMO only.",
    })

    for schema in (TEMPLATE / "schema").glob("*.json"):
        shutil.copy2(schema, OUTPUT / "schema" / schema.name)

    artifacts = []
    for path in sorted(OUTPUT.rglob("*")):
        if path.is_file() and path.name != "delivery_manifest.json":
            artifacts.append({
                "path": path.relative_to(OUTPUT).as_posix(),
                "sha256": sha256(path), "size_bytes": path.stat().st_size,
            })
    manifest = {
        "contract": {"name": "pfc.standardized-experiment", "version": "1.0.0",
                     "schema_version": "1.0.0", "immutable": True,
                     "scope": "STANDARDIZED_EXPERIMENT_DATA"},
        "producer": {"skill": "pfc-scientific-visualization", "entrypoint": "build_fullcapability_mock"},
        "experiment": {"path": "experiment.json",
                       "sha256": sha256(OUTPUT / "experiment.json"),
                       "size_bytes": (OUTPUT / "experiment.json").stat().st_size},
        "raw_input": {"root": "GENERATED", "read_only": True,
                      "embedded_in_contract": False, "input_file_count": 0},
        "consumer_policy": {"read_only": True, "may_write_inside_contract": False},
        "cases": [{"case_id": 0,
                   "conversion_report": "cases/case_0/conversion_report.json",
                   "arrays": "cases/case_0/arrays.npz",
                   "arrays_sha256": sha256(npz_path)}],
        "artifacts": artifacts,
    }
    dump(OUTPUT / "delivery_manifest.json", manifest)

    print(f"Built MOCK full-capability package: {OUTPUT}")
    print(f"  frames={FRAMES} balls/frame={BALLS} events={n_events}")
    print(f"  contact pairs/frame={len(c_a)//FRAMES} bond pairs/frame={len(b_a)//FRAMES}")
    print("  channels: ball, wall-face, dynamic-fracture, contact-network, bond-network")
    return 0


def _neighbour_pairs(balls: int, grid_n: int, rng: np.random.Generator):
    pairs = []
    # horizontal + vertical neighbours on the grid, capped for payload size
    for i in range(0, balls - 1, 3):
        if i % grid_n < grid_n - 1:
            pairs.append((i + 1, i + 2))
        if i + grid_n < balls:
            pairs.append((i + 1, i + grid_n + 1))
    return pairs[:120]


if __name__ == "__main__":
    raise SystemExit(main())
