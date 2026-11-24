# Data Lifecycle and Cleanup

## Ownership split

Raw capture, standardized arrays and `delivery_manifest.json` are owned by
`pfc-headless`. This Skill's cleanup command rejects a standardized contract
root and only accepts an analysis-output root containing `03_analysis/` or
`04_viewer/`.

## Analysis-output classes

| Class | Examples | Policy |
|---|---|---|
| `external source` | pfc-headless raw/standardized contract | read-only; never cleanup targets |
| `intermediate` | failed attempts, temporary exports, caches, staging trees | eligible only through an explicit cleanup plan |
| `processed` | analysis arrays and chart specifications | preserve with the analysis result |
| `deliverables` | Viewer, publication figures, metadata, reports | retain for delivery |

## Protected evidence

`scripts/cleanup_delivery.py` protects these directory names and suffixes:

```text
01_raw_data 02_standardized_data 03_analysis 04_viewer
05_charts 06_publication_figures 07_metadata report

.sav .prj .dat .fis .his .p2dat .p3dat
```

Any candidate that recursively contains protected evidence is skipped.

## Workflow

1. Generate a dry-run JSON plan.
2. Review accepted and skipped paths and file hashes.
3. Re-run with `--apply --confirm CLEAN_INTERMEDIATE` only after approval.
4. The tool writes `07_metadata/cleanup_report.json`.

The cleanup tool never starts PFC, edits the standardized contract, or removes
analysis/Viewer deliverables.

## Delivery rule

The final Viewer is an offline directory bundle. A delivery is incomplete if
only `scientific_viewer.html` is copied without its adjacent `viewer/` and
`data/` directories.
