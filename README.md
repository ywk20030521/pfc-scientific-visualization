# PFC Scientific Visualization

An installable scientific post-processing Skill for verified PFC2D/PFC3D
standardized data. It consumes the immutable
`pfc.standardized-experiment@1.0.0` contract produced by `pfc-headless` and
creates:

- derived physical quantities and statistics with formula lineage;
- unit-aware analysis and display formatting;
- explainable, data-driven chart selection;
- an offline Three.js/ECharts Viewer;
- adaptive publication-figure planning and vector composition;
- explicit 2D/3D linkage decisions;
- a status-honest analysis result package.

This Skill does not run PFC, access the Console bridge, capture raw files,
perform raw quality checks or standardize captured files.

## Quick start

1. Obtain a validated standardized experiment from `pfc-headless`. It must
   contain `delivery_manifest.json`, `experiment.json` and per-Case
   `arrays.npz`.
2. Analyze, select charts and build the Viewer:

   ```powershell
   & "<python>" "<skill>\scripts\run_pipeline.py" `
     --input "<StandardizedExperiment>" `
     --output "<AnalysisResult>" `
     --max-frames 0
   ```

3. Open `04_viewer/scientific_viewer.html` together with its adjacent
   `viewer/` and `data/` directories.
4. Review `03_analysis/chart_decisions.json`,
   `03_analysis/data_layers.json`, `07_metadata/source_contract.json`,
   `07_metadata/output_contract.json` and `report/experiment_report.md`.

See [SKILL.md](SKILL.md) and
[references/standardized-input.md](references/standardized-input.md).

## Responsibility boundary

`pfc-headless` owns PFC execution, real capture, raw preservation, integrity
checks, metadata management and standardized delivery.

This Skill owns scientific derivations, statistics, analytical conversions,
chart selection, rendering and publication output.

The standardized input is always read-only. Analysis output must use a separate
directory and never contains duplicate `01_raw_data/` or
`02_standardized_data/` trees.

## Data and visual boundaries

Missing values are never replaced by zeros, synthesized frames or plausible
geometry. Every channel carries `REAL_PFC`, `DERIVED`, `CONFIG`,
`NOT_CAPTURED` or `INVALID`. Generated files can still be `NOT_VERIFIED`.

The Viewer uses one shared state for Case, real frame, Cycle, time, Ball
selection, metric and range. PFC2D uses planar `CircleGeometry`, PFC3D uses
level-of-detail `SphereGeometry`, and all particles use a reused `InstancedMesh`.

The Viewer is **light-only**: the dark theme, the theme toggle and `?theme=dark`
were removed. All colors are centralized in
`assets/styles/scientific-visual-semantics.json` under `themes.light`. The
scene uses ACES tone mapping with quantitative instance colors opted out of
tone mapping, a physical-material particle preset, rim light and a local
equirectangular environment map. The default Nature ramp is bright and
publication-friendly; a high-contrast ramp is selectable in the bottom control
dock but is not the default. All Three.js controls live in a collapsed-by-default
bottom dock, and the right rail contains charts only. The render:chart split is
the golden ratio (1.618:1). Export backgrounds remain white or transparent.

The split was reaccepted on 2026-11-16 against a pfc-headless standardized
contract: the unit/contract suite reports 61 PASS and real PFC2D/PFC3D browser
regressions passed. Genuinely open items are listed in
[tests/UNVERIFIED_ITEMS.md](tests/UNVERIFIED_ITEMS.md) and the updated
[CAPABILITY_MATRIX.md](CAPABILITY_MATRIX.md): hardware performance is still
unmeasured, real endpoint-array network rendering and clump membership have no
captured evidence, and PDF output needs a local vector converter. The
[IMPLEMENTATION_REPORT.md](IMPLEMENTATION_REPORT.md) describes the earlier
integrated build and is not the current acceptance record.

## Observability, packaging and feedback verification (2026-11-24)

All additions are opt-in or additive; standardized inputs and analysis outputs
are unchanged. See `reports/UPGRADE_V0_V3_2026-11-24.md` for the full record.

- `run_pipeline.py --measure [--warm]` writes
  `07_metadata/stage_timings.json`: 7 stage durations, RSS (ctypes/psapi,
  no new dependency), tracemalloc, and input/output bytes. The report is itself
  included in `output_index.json` hashes.
- `performance_baseline.py freeze|check` records environment-tagged baselines
  and detects regressions (+20% warning, +50% failure, RSS budget, input hash).
- `package_experiment.py --package scientific|display` builds a hash-verified
  package in a temp file and publishes atomically. `display` contains only
  `04_viewer` and `05_charts`, no raw or standardized scientific data.
- `verify_feedback_loop.py` proves findings → headless ingest/approve/
  prepare-run on an isolated project copy: new Run differs from source Run and
  the source Run files remain byte-identical.
- Cleanup refuses directories whose files are claimed by `output_index.json`.

RSS and tracemalloc measure different scopes; they are reported side by side and
must not be added together.
