# Standardized NumPy Input Format

`pfc-headless` produces each Case as one compressed `arrays.npz`. This Skill
reads the NPZ and never replaces it with a rectangular array or rewrites it.

`pfc-headless/run_standardization.py --export-npy` may also write independent
`.npy` arrays below `cases/case_N/npy/`. The NPZ archive remains the canonical
contract input.

## Required frame arrays

| Key | Dtype | Shape | Meaning |
|---|---|---|---|
| `cycle` | `int64` | `(F,)` | PFC Cycle |
| `mechanical_time_total` | `float64` | `(F,)` | Total mechanical time in seconds |
| `frame_offsets` | `int64` | `(F+1,)` | Ball slice boundaries |
| `ball_id` | `uint64` | `(Eb,)` | Stable IDs for all real frame entries |
| `ball_xyz` | `float64` | `(Eb,3)` | Coordinates |
| `ball_radius` | `float64` | `(Eb,)` | Observed/current radius |
| `ball_frame_index` | `int64` | `(Eb,)` | Frame index of each entity row |
| `wall_offsets` | `int64` | `(F+1,)` | Wall-vertex slice boundaries |
| `wall_id` | `uint64` | `(Ew,)` | Wall identity |
| `wall_vertex_id` | `uint64` | `(Ew,)` | Vertex identity within its Wall |
| `wall_vertex_xyz` | `float64` | `(Ew,3)` | Same-frame vertex coordinates |

Frame `f` owns Ball rows
`frame_offsets[f]:frame_offsets[f+1]`. `Eb` is the total number of Ball
observations across frames, not a fixed frame count. Never reshape using an
assumed particle count.

## Events

The fracture arrays are empty if no fracture channel was captured:

- `fracture_event_id`
- `fracture_cycle`
- `fracture_mechanical_time_total`
- `fracture_mode`
- `fracture_position` `(E,3)`
- `fracture_normal` `(E,3)`
- `fracture_diameter`

Mode `1` is tension in the preserved capture convention; mode `2` is shear.
If this convention changes, it must be declared in the conversion report.

## Optional frame channels

`top_force_n`, `bottom_force_n`, `platen_distance_m`, and native History arrays
are written only when they exist. Missing optional keys are not replaced with
zero arrays.

## Optional network arrays

The Viewer can render contact or Bond networks only when the standardized case
contains same-frame endpoint IDs:

| Prefix | Required keys |
|---|---|
| `contact` | `contact_frame_offsets`, `contact_ball_id_a`, `contact_ball_id_b` |
| `bond` | `bond_frame_offsets`, `bond_ball_id_a`, `bond_ball_id_b` |

Optional `contact_force_n` and `bond_force_n` arrays provide per-connection force
magnitudes for line coloring. Endpoint IDs are resolved against the Ball ID set
of the same real frame. Missing endpoints are skipped; no connection is
inferred from proximity or Wall aggregate force.

## Sidecars

- `case.json`: schema record and provenance.
- `channels.json`: data-supported Channel Inventory.
- `frames.json`: frame IDs, Cycles, times and offsets.
- `events.json`: event records.
- `entity_changes.json`: added/removed Ball IDs and radius changes per real frame.
- `frame_summary.csv`: readable per-frame Cycle/time/counts and optional force
  or platen channels; blank cells mean unavailable.
- `conversion_report.json`: input/output hashes, shapes, dtypes, source markers,
  missing fields and status.

## Integrity rules

- Frame IDs and Cycles are strictly increasing.
- `len(cycle) == len(mechanical_time_total) == F`.
- `len(frame_offsets) == F + 1`.
- `frame_offsets[0] == 0`.
- `frame_offsets[-1] == len(ball_id)`.
- IDs are unique inside each real frame.
- Each declared Ball count equals the offset length.
- No non-finite coordinate is accepted as valid capture data.
