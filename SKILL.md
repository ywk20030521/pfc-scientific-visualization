---
name: pfc-scientific-visualization
description: Analyze verified PFC2D/PFC3D standardized experiment data, derive scientific quantities, calculate statistics and analytical transforms, select explainable charts, build an offline Three.js/ECharts Viewer, and compose traceable analysis results. Use after pfc-headless has produced the immutable standardized-data contract.
metadata:
  short-description: Scientific analysis and visualization of standardized PFC data
---

# PFC Scientific Visualization

Consume the immutable `pfc.standardized-experiment@1.0.0` contract produced by
`pfc-headless`, then own scientific analysis, statistics, analytical
transformations, chart decisions, Viewer generation, publication figures and
the resulting analysis package.

This Skill does not run PFC, start a Console or Bridge, capture raw frames,
perform raw quality checks or standardize captured files. It must not modify
the standardized input tree.

## Responsibility boundary

This Skill owns:

- derived physical quantities;
- statistics and analytical conversions;
- Chart Intelligence decisions;
- Three.js/ECharts presentation;
- linked interaction state;
- publication composition;
- analysis provenance, reports and acceptance status.

`pfc-headless` owns:

- simulation execution and capture;
- raw files and integrity evidence;
- Case/Frame/Cycle/time/entity metadata;
- standardized arrays and delivery manifest.

## Non-negotiable truth rules

- Verify the standardized contract and artifact hashes before analysis.
- Treat the complete standardized root as read-only.
- Write analysis output to a separate directory.
- Never fabricate, interpolate, zero-fill or silently repair source data.
- Derive a quantity only when all required inputs and a unit basis exist.
  Record formula, inputs, source, unit, method, applicability and version.
- Preserve dynamic entity ID sets; never force a fixed `(T,N,3)` shape.
- Do not interpret an unfamiliar History name as stress, strain, force or any
  other physical quantity without explicit metadata.
- Viewer playback switches only among real frames in the standardized contract.
- Display rounding never becomes an analysis input.
- Use `NOT_VERIFIED` until the relevant browser, export, integration or
  performance acceptance has run.

## Workflow

1. **Verify the input contract.** Require `delivery_manifest.json`,
   `experiment.json`, per-Case `arrays.npz` and matching hashes. Reject a raw
   capture directory or an incomplete standardized tree. Read
   [references/standardized-input.md](references/standardized-input.md).
2. **Analyze and transform.** Use the declared channels, units, geometry and
   frame offsets. Run:

   ```powershell
   & "<python>" "<skill>\scripts\run_pipeline.py" `
     --input "<StandardizedExperiment>" `
     --output "<new-analysis-result-directory>" `
     --max-frames 0
   ```

   Read [references/analysis-engine.md](references/analysis-engine.md) and
   [references/numpy-data-format.md](references/numpy-data-format.md).
3. **Select charts from evidence.** Omit a chart when a channel is absent,
   invalid, constant where variation is required, too sparse or physically
   misleading. Record selected type, score, reason, alternatives, missing data
   and derivation status. Read
   [references/chart-intelligence.md](references/chart-intelligence.md).
4. **Render offline.** Build `04_viewer/scientific_viewer.html` with local
   Three.js/ECharts assets. Use `CircleGeometry` for PFC2D and
   `SphereGeometry` for PFC3D. Preserve real coordinates, dimensions and frame
   IDs. Read [references/threejs-rendering.md](references/threejs-rendering.md)
   and [references/viewer-state-and-performance.md](references/viewer-state-and-performance.md).
5. **Compose publication figures.** Use the Nature-inspired ECharts system and
   content-aware composition. Read
   [references/echarts-chart-system.md](references/echarts-chart-system.md),
   [references/nature-visual-design-system.md](references/nature-visual-design-system.md)
   and [references/figure-composition.md](references/figure-composition.md).
6. **Decide linkage explicitly.** Shared time and Case state are implemented.
   Projection, camera or bidirectional graph linkage requires a documented
   scientific and interaction decision. Read
   [references/linkage-decisions.md](references/linkage-decisions.md).
7. **Verify and report.** Run payload, browser and export gates when
   authorized. Artifact creation alone is `NOT_VERIFIED`. Populate the analysis
   output contract with actual files, absent outputs, support limits and
   acceptance evidence. See
   [references/output-contract.md](references/output-contract.md).
8. **Emit analysis feedback.** Generate the stable Findings contract from the
   completed analysis:

   ```powershell
   & "<python>" "<skill>\scripts\emit_findings.py" `
     --analysis-root "<AnalysisResult>" `
     --project-root "<HeadlessProject>" `
     --output "<HeadlessProject>\analysis\findings\<run>_findings.json"
   ```

   The producer records the source manifest hash, referenced analysis
   artifacts, unavailable channels and recommended collection plan. When
   `--project-root` is supplied and the analysis root lives outside that
   project (the normal boundary), the three referenced JSON artifacts are
   copied into `<project-root>/analysis/findings/<feedback_id>/artifacts/` and
   recorded with SHA-256 hashes; their paths in the contract are then relative
   to the project root so headless ingestion accepts them. Use
   `--no-copy-artifacts` to keep the previous path behavior. Headless owns
   ingestion and approval; this Skill does not create the next Run.

   Browser verification treats Ball history as a subset of the real Viewer
   frames when a Ball is absent from some frames (dynamic entity ID sets). It
   validates the source/viewer/Cycle mapping of every reported row instead of
   demanding a fabricated full-length history.

## Three analysis layers

The standardized input is an external immutable parent.

| Layer | Owner | Contract |
|---|---|---|
| `RAW_DATA` | `pfc-headless` | Captured evidence and hashes; referenced read-only |
| `ANALYSIS_DATA` | this Skill | Explicit operations on standardized arrays |
| `DISPLAY_DATA` | this Skill | Formatting and unit display only |

Every local analysis layer records its external parent manifest and artifact
hashes. See [references/data-layers.md](references/data-layers.md).

## Chart Intelligence rules

- Use field metadata, unit, source, dimensions, completeness and aligned
  structure; a field name alone is insufficient.
- Generate candidates only after data and meaning gates pass.
- Supported families include line/area, scatter, spatial/time heatmap,
  bar/grouped/stacked bar, histogram/boxplot, rose/polar, correlation heatmap
  and radar when the data genuinely supports them.
- Record rejected candidates and why they were not generated.
- Manual overrides are valid only when compatible with the data structure.

## Standard analysis output

```text
<AnalysisResult>/
|-- 03_analysis/
|   |-- analysis.json
|   |-- chart_specs.json
|   |-- chart_decisions.json
|   |-- display_data.json
|   `-- data_layers.json
|-- 04_viewer/
|   |-- scientific_viewer.html
|   |-- viewer/
|   |-- data/
|   `-- linkage_decisions.json
|-- 05_charts/
|-- 06_publication_figures/
|-- 07_metadata/
|   |-- source_contract.json
|   |-- experiment_capabilities.json
|   |-- output_contract.json
|   `-- output_index.json
`-- report/experiment_report.md
```

The separately emitted `pfc.analysis-findings@1.0.0` file is the feedback
contract consumed by `pfc-headless`. Its schema is
`schema/analysis_findings.schema.json`.

There are intentionally no new `01_raw_data/` or `02_standardized_data/`
directories in this Skill's output. Those artifacts remain owned by
`pfc-headless`.

The generated Viewer is light-only. Three.js controls live in a collapsed
bottom dock; the right rail contains charts only; the render:chart split uses
the golden ratio (1.618:1). To share a run, package the whole `04_viewer/`
directory (HTML + `viewer/` + `data/`) as ZIP with
`scripts/viewer/package_viewer.py` — sending only the HTML will not work.

## Status vocabulary

| Status | Meaning |
|---|---|
| `GENERATED` | File or result was actually produced |
| `NOT_GENERATED` | Not produced |
| `NOT_CAPTURED` | The standardized source did not include the field or entity |
| `NOT_SUPPORTED` | Current analysis or visual implementation cannot produce it |
| `INVALID` | Integrity or physical-validity check failed |
| `NOT_VERIFIED` | Generated or implemented without the required acceptance run |

Always report code implemented, tests executed, missing channels, unsupported
capabilities, exact generated files and acceptance evidence separately.

## References

- [examples/reference_3d_case/confined_break_6k/README.md](examples/reference_3d_case/confined_break_6k/README.md):
  primary complete real-data reference case (raw run + standardized delivery +
  analysis/viewer). Mock showcases are regression fixtures only.
- [MODULE_EVALUATION_2026-11-24.md](MODULE_EVALUATION_2026-11-24.md): latest
  module-level performance evaluation and acceptance evidence.
- [references/standardized-input.md](references/standardized-input.md): read-only
  contract received from `pfc-headless`.
- [references/architecture.md](references/architecture.md): component boundaries.
- [references/data-layers.md](references/data-layers.md): external raw parent
  and local analysis/display lineage.
- [references/numpy-data-format.md](references/numpy-data-format.md): NPZ keys
  and offsets.
- [references/analysis-engine.md](references/analysis-engine.md): formulas and
  analysis limits.
- [references/chart-intelligence.md](references/chart-intelligence.md): chart
  decisions.
- [references/threejs-rendering.md](references/threejs-rendering.md): 3D design
  system.
- [references/viewer-state-and-performance.md](references/viewer-state-and-performance.md):
  state and performance.
- [references/echarts-chart-system.md](references/echarts-chart-system.md):
  scientific ECharts.
- [references/nature-visual-design-system.md](references/nature-visual-design-system.md):
  visual tokens.
- [references/figure-composition.md](references/figure-composition.md): adaptive
  multipanel layout.
- [references/linkage-decisions.md](references/linkage-decisions.md): linkage
  policy.
- [references/output-contract.md](references/output-contract.md): analysis
  output status contract.
- [references/data-lifecycle.md](references/data-lifecycle.md): cleanup
  boundaries.

## Delivery limits

Analysis and Viewer acceptance require a verified standardized contract. Code
presence and generated files are not runtime success. New data still requires
browser, export, integration and performance acceptance after the standardized
source changes.
