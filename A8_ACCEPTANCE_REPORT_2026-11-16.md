# A8 Acceptance Report

## Decision

A8 is `PASS` for this stage. A1-A4 remained frozen and passed their strict Mock
and real PFC3D regression scenarios after the A8 changes.

## Implemented contract

The analysis engine now emits one availability record per multi-Case metric:

- `total_case_count`;
- `available_case_count`;
- `missing_case_count`;
- `missing_case_ids`;
- per-Case `value`, `state` and failure reason;
- `comparable` and `not_comparable_reason`.

Chart Intelligence validates this contract and refuses inconsistent counts. The
chart decision and chart spec now carry the exact missing count instead of a
default zero.

Multi-Case charts use one color per metric semantic:

| Metric | Color |
|---|---|
| Stress | `#3C5488` |
| Displacement | `#8491B4` |
| Crack count | `#E64B35` |

No four-color cycle is used. Missing bars remain null, missing Case labels use
the neutral missing color, and the panel reports `可用 N/M · 缺失 K`.

## Real PFC3D evidence

`REAL_PFC` Case comparison result:

```text
Stress:        total 23, available 2, missing 21
Displacement:  total 23, available 23, missing 0
Stress missing Case IDs:
0,1,2,3,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22
```

The Viewer rendered exactly 21 null stress bars and one stress color
`#3C5488`. No missing bar was converted to zero.

## Verification

- Scientific suite: `47 PASS, 0 FAIL`.
- A1-A4 strict Mock browser regression: `PASS`, including 351-to-8 frame
  mapping, Ball history, Case switch and 12 actual SVG downloads.
- A1-A4 + A8 real PFC3D browser regression: `PASS`.
- Real PFC3D downloads: 10 unique SVG files, matching titles and SVG roots.
- No new PFC solve was started.

## Evidence

```text
C:\Users\L\.codex\visualizations\2026\11\16\01a1e448-7bfd-7923-ad01-b03e22dea4fe\a8-real-pfc3d
C:\Users\L\.codex\visualizations\2026\11\16\01a1e448-7bfd-7923-ad01-b03e22dea4fe\a8-browser-final
C:\Users\L\.codex\visualizations\2026\11\16\01a1e448-7bfd-7923-ad01-b03e22dea4fe\a8-a1-a4-mock-browser
```

## Next stage

A6 may now begin. A5 and A9/A7 are not part of this report and remain
`NOT_VERIFIED`.
