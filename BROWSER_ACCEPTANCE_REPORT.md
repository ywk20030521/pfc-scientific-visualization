# Viewer Browser Acceptance

> Historical snapshot from an earlier Viewer build. The current upgraded Viewer
> was not run in a browser during this delivery.

Environment: local headless Microsoft Edge with SwiftShader at 1600×1000.

| Check | PFC2D | PFC3D |
|---|---|---|
| Page ready | PASS | PASS |
| Offline dependency gate | PASS | PASS |
| External network requests | none | none |
| Real-frame timeline | PASS | PASS |
| Chart drag updates unified frame | PASS | PASS |
| Rendered-particle click | Ball `26` | Ball `275` |
| Selected-Ball history | PASS | PASS |
| Distribution range highlight | PASS | PASS |
| Specified-frame PNG | PASS | PASS |
| Chart SVG export | 7 SVG | 7 SVG |
| Composite PNG | PASS | PASS |
| Browser exceptions | none | none |
| Case switch | `NOT_APPLICABLE_SINGLE_CASE` | `NOT_APPLICABLE_SINGLE_CASE` |
| Dedicated two-Case switch | `PASS` | `PASS` |

The single-Case runs explicitly report `NOT_APPLICABLE_SINGLE_CASE`. A separate
result assembled from two real Console captures was browser-tested with Case 1
as the default and a switch to Case 0. Frame, Cycle, selection and range reset
correctly; dynamic additions and removals were counted from each Case's own
static set, not from another Case.

Exported files are written under
`06_publication_figures/browser_exports/`.
