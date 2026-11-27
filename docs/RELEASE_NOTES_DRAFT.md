# Release Notes — DRAFT (not published)

**Repository:** `ywk20030521/pfc-scientific-visualization`
**Proposed tag:** `v2.1.0` — **NOT CREATED**
**Status:** `DRAFT / BLOCKED`
**Date:** 2026-11-27

## 1. Status

This is a release-note draft for the first public Git tag. No tag and no
GitHub Release exist. Historical packaging referenced a `v2.1` ZIP; that is a
package label, not a published Git tag.

## 2. Release blockers

| Blocker | Evidence | Required action |
|---|---|---|
| `analysis-findings` naming and marker fix not on `main` | REM-001 R05, in `fix/audit-remediation` worktree | Merge and verify both Viz and Headless schema acceptance |
| Canonical layer vocabulary not on `main` | REM-001 R06, remediation worktree | Merge; verify `normalize_layer()` with Headless |
| One test ERROR in a fresh worktree | REM-001 §4: `test_standard_contract_boundary` hash mismatch under `core.autocrlf=true` | Re-run after merge in the main workspace; do not tag while red |
| Hard-coded Headless project root / owner | REM-001 R12 | Parameterize `project_root` / `owner` / `artifact_root` |
| Cross-Skill invocation envelope undefined | REM-001 R11 | Agree `pfc.skill-invocation@1.0.0` with Interaction and Execution |

## 3. Capabilities on the current baseline

- Offline Three.js / ECharts Viewer with local assets and no runtime CDN calls.
- Derived quantities, unit-aware statistics and formula lineage.
- Chart Intelligence, publication figure composition and 2D/3D linkage decisions.
- Consumption of `pfc.standardized-experiment@1.0.0` from `pfc-headless`.

## 4. Verification evidence

`TEST_REPORT.md`, `VALIDATION_REPORT.md`, `BROWSER_ACCEPTANCE_REPORT.md`,
`A5-A9_FINAL_ACCEPTANCE_REPORT_2026-11-16.md`.
These describe the environment in which they were produced; they are not a
verification of this draft tag.

## 5. Verification to repeat before publishing

```bash
PYTHONPATH=scripts python -m unittest discover -s tests -p "test_*.py"
```

Then repeat the browser/offline Viewer check on a real standardized dataset,
and record the exact commit. If a worktree hash mismatch appears, re-run in the
main workspace and resolve line-ending handling before tagging.

## 6. Known limitations

- Independent-machine and static hosting remain `NOT_VERIFIED`.
- ZIP compression ratio is not runtime memory; report JS heap, GPU estimate and
  peak memory separately.
- Analysis feedback is not a scientific Finding; model validation belongs to
  the Research Evidence Skill.
