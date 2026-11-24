# Analysis Schema and Standardized Input

The standardized experiment schema is owned by `pfc-headless` and embedded in
the delivered input contract. This Skill validates that contract before use.

Output-side chart, linkage, Viewer-state and data-layer schemas remain in
`schema/`. The current shared contract version is `1.0.0`.

## Core records

- **Experiment, Case, Channel, Frame and captured provenance** are received from
  the pfc-headless standardized contract.
- **Analysis result**: derived channel, formula, input references, unit,
  method and applicability.
- **Analysis layer**: local output artifacts and external standardized parent.
- **Display layer**: formatting-only metadata derived from analysis values.
- **ViewerState**: the single browser interaction state shared by timeline,
  Three.js scene, ECharts charts and selection panels. Its interchange schema is
  `schema/viewer_state.schema.json`.
- **Data layer**: external RAW parent plus local ANALYSIS_DATA or DISPLAY_DATA
  identity, artifacts, operations and provenance. See
  [data-layers.md](data-layers.md).
- **Chart decision**: source channels, analysis goal, selected type, score,
  reason, alternatives, missing count and override result
  (`schema/chart_decision.schema.json`).
- **Linkage decision**: scientific need, user value, technical/data complexity,
  performance/maintenance cost and implementation status
  (`schema/linkage_decision.schema.json`).

## Data source classes

| Value | Use |
|---|---|
| `REAL_PFC` | Directly captured from a real PFC run |
| `DERIVED` | Computed from declared inputs |
| `CONFIG` | User/project configuration or a non-PFC fixture |
| `NOT_CAPTURED` | Source was unavailable in the experiment |
| `INVALID` | Data failed validity or integrity checks |

The experiment-level `data_boundary` is `REAL_PFC`, `MOCK`, `MIXED` or
`UNKNOWN`. It is separate from per-channel source labels.

## Dynamic entities

Do not represent all frames as one rectangular array. Each frame points into
concatenated entity arrays with offset pairs. A Ball can therefore appear in
frame 1, disappear in frame 2, or be added in frame 3 without changing the
shape of the whole dataset.

Every first observation of a newly added Ball is real. A displacement reference
may use that first observation, but this must be stated as a derived reference;
the Viewer must not imply that the Ball existed in the previous frame.

## Validation

`standard_contract.py` verifies the pfc-headless manifest, artifact hashes,
Case array hashes, core NPZ keys and frame-offset lengths. A schema-valid object
is not necessarily a physically verified result; runtime verification remains
separate.

## Visual semantics

`assets/styles/scientific-visual-semantics.json` maps declared variable families
to entity type, color token and scale type. Unknown fields do not receive a
physical color meaning.
