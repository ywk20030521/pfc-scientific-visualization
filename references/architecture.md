# Architecture

The system is split into two Skills with a versioned data boundary.

```text
PFC Console execution and capture              [pfc-headless]
  -> immutable raw files + integrity evidence  [pfc-headless]
  -> quality checks + metadata                 [pfc-headless]
  -> variable-length NPZ + schema              [pfc-headless]
  -> delivery_manifest.json                    [pfc-headless]
  ================= CONTRACT BOUNDARY =================
  -> derived quantities + statistics           [pfc-scientific-visualization]
  -> chart decisions + specifications          [pfc-scientific-visualization]
  -> offline Three.js + ECharts Viewer         [pfc-scientific-visualization]
  -> publication composition + report          [pfc-scientific-visualization]
```

The input contract is
`pfc.standardized-experiment@1.0.0`. The analysis output is a separate tree
with no duplicate raw or standardized directories.

## Scientific module boundaries

| Module | Responsibility | Must not do |
|---|---|---|
| `standard_contract.py` | Verify the read-only standardized manifest, hashes and core arrays | Repair or write inside the input contract |
| `analysis/` | Register channels, derive quantities, compute statistics and select charts | Infer physical meaning from a History name |
| `analysis/formatting.py`, `units.py` | Format display values and declare conversions | Mutate analysis arrays or become analysis input |
| `viewer/payload_builder.py` | Create catalog, frame chunks and Ball-history buckets | Synthesize missing frames |
| `viewer/external_builder.py` | Bundle the offline HTML shell, app code and local dependencies | Embed the full experiment in the HTML |
| `viewer/linkage.py` | Record linkage decisions | Force unsupported bidirectional linkage |
| `verify_payload.py` | Compare Viewer payload values with standardized arrays | Treat sampling as exhaustive proof |
| `verify_lazy_viewer.mjs` | Exercise timeline, chart, Ball and range interactions | Accept without visual evidence |
| `charts/` | Publication planning and vector composition | Invent absent panels |
| `packaging/` | Materialize analysis output and hash files | Convert ungenerated items into generated items |

## Handoff invariants

- Analysis output root is separate from the standardized input root.
- The delivery manifest and every artifact hash are verified before analysis.
- `source_contract.json` records the input identity and read-only policy.
- `ANALYSIS_DATA` references the pfc-headless contract as its external parent.
- `DISPLAY_DATA` references local analysis and is never used as an analysis
  input.
- Temporal views index captured records; no missing frame is synthesized.
- Entity allocation follows dynamic ID offsets from the standardized contract.
- Scientific capabilities are inspected per Case so one missing optional field
  does not block unrelated Cases.

## Stable boundaries

- PFC execution and Console-bridge code do not exist in this Skill.
- Viewer generation never starts PFC.
- Quality checking and standardization happen before this Skill receives data.
- Analysis never mutates standardized arrays.
- The scientific Viewer uses one interaction store; frame chunks and selected
  Ball histories remain external local files.
