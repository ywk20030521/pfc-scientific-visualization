# A5-A9 Final Acceptance Report

## Decision

A5-A9 are `PASS` as staged repairs. A1-A4 remained frozen and passed the final
strict Mock and real PFC3D regressions.

| Stage | Result | Report |
|---|---|---|
| A8 multi-Case availability | `PASS` | `A8_ACCEPTANCE_REPORT_2026-11-16.md` |
| A6 axis contract | `PASS` | `A6_ACCEPTANCE_REPORT_2026-11-16.md` |
| A5 robust histograms | `PASS` | `A5_ACCEPTANCE_REPORT_2026-11-16.md` |
| A9 identity mapping | `PASS` | `A9_A7_ACCEPTANCE_REPORT_2026-11-16.md` |
| A7 publication presentation | `PASS` | `A9_A7_ACCEPTANCE_REPORT_2026-11-16.md` |

## Required boundaries

- No finite observation is silently removed from multi-Case availability or
  robust histograms.
- Missing values are not treated as zero.
- SVG identity is resolved by stable chart ID or unique title, never by file
  position.
- Axis notation and zero policy are explicit per axis.
- Publication figures select high-value charts per Case instead of placing all
  analysis charts into one canvas.
- A1-A4 frame mapping, missing-value semantics and real download scheduling were
  not refactored.

## Final verification

- Scientific test suite: `61 PASS, 0 FAIL`.
- Python compilation and JavaScript syntax checks: `PASS`.
- A1-A4 strict Mock browser regression: `PASS`.
- Real PFC3D A1-A9 browser regression: `PASS`.
- Real SVG download: 10 unique files, matching title and chart identity.
- A5 analysis/live distribution: 2,296 finite values with 115 low-tail and 115
  high-tail observations.
- A8 pressure comparison: 2/23 available, 21 missing Cases, exact IDs reported.
- Publication plan: 129 analysis charts, 125 selected, 4 omitted, 24 figure
  groups, maximum 6 panels per group.
- Case 22 composed figure: six panels, `(a)`-`(f)`, no outside-root text, no
  duplicate titles and all identities resolved by embedded chart ID.

## Final evidence

```text
C:\Users\L\.codex\visualizations\2026\11\16\01a1e448-7bfd-7923-ad01-b03e22dea4fe\a5-a9-final
C:\Users\L\.codex\visualizations\2026\11\16\01a1e448-7bfd-7923-ad01-b03e22dea4fe\a5-a9-final-browser
C:\Users\L\.codex\visualizations\2026\11\16\01a1e448-7bfd-7923-ad01-b03e22dea4fe\a5-a9-final-compose
C:\Users\L\.codex\visualizations\2026\11\16\01a1e448-7bfd-7923-ad01-b03e22dea4fe\a5-a9-final-mock-browser
```

## Remaining limits

- No new PFC solve was executed.
- Hardware-GPU performance was not re-benchmarked.
- PFC2D A15 acceptance remains outside this round.
- A10-A15 are not claimed complete.
- PDF output still requires a local vector converter.
