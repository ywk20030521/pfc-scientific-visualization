# Reference 3D Case — Confined Break 6k

This directory is the primary real-data reference case for the skill. It replaces the former mock showcase as the example that should be read first when understanding a complete PFC3D pipeline. Mock fixtures remain only as small unit-test inputs.

Run ID: `run_case17_confined_break_6k_r1`

## Contents

- `01_raw_data/` — complete immutable PFC run directory: configuration snapshot, setup script, raw ball/wall/fracture/frame CSV files, result and validation metadata.
- `02_standardized_data/` — immutable `pfc.standardized-experiment@1.0.0` delivery produced by `pfc-headless`.
- `03_analysis_viewer/` — complete visualization-skill output: analysis, charts, viewer, payload, metadata and experiment report.

This is a complete case, not a single `case.json` config.

## Model summary

- PFC3D 9.0 Console
- 6379 balls, radius `0.014–0.020`
- six finite walls: top/bottom platens plus four rigid lateral confinement walls
- 500 settling cycles before bonding
- `contact method bond gap 0.0012`
- staged displacement-rate loading
- `pb_ten=5.0e5`, `pb_coh=1.5e6`
- 19 real frames, 3721 FISH bond-break events with endpoint Ball IDs

## Validation evidence

- Headless data contract: `PASS []`
- Viewer payload: `PASS []`
- Browser: `wallFaces=72`, `cracks=3407` at cycle 4500, no pageerror
- Headless tests: 63 OK
- Visualization tests: 75 OK

## Known limits

- Contact network was not captured in this run; contact channel is `NOT_CAPTURED`.
- A small number of particles can still pass above the top platen in z; x/y lateral confinement is effective.
- This case prioritizes observable fracture and stable computation. It is **not** a validated 150 MPa granite UCS calibration.
