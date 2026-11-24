# A6 Acceptance Report

## Decision

A6 is `PASS` for this stage. A1-A4 remained frozen and passed the strict Mock
and real PFC3D regression scenarios after the axis changes.

## Implemented axis contract

Chart specs now carry an axis contract for each numerical axis:

- `include_zero`;
- `range_policy`;
- observed finite minimum and maximum;
- notation (`DECIMAL` or `SCIENTIFIC_SHARED_EXPONENT`);
- shared exponent, scale and scale label;
- tick decimals.

The Viewer applies the axis contract directly. It no longer decides scientific
notation independently for every tick.

## Range policy

- Positive-only line/scatter axes use a padded data extent and do not force zero.
- Area charts, bars, counts and comparisons include zero.
- Axes whose observed range crosses zero also include zero.

No numeric observations are removed or replaced to set the range.

## Real PFC3D evidence

Case 22 speed:

```text
range policy: DATA_EXTENT_PADDED
include zero: false
y ticks: 0.012 ... 0.020 s
```

Case 22 average displacement:

```text
range policy: ZERO_INCLUDED
axis label: 平均位移 (m) [× 10⁻⁴]
tick labels: 0, 0.5, 1, 1.5, ... 3.5
```

Every scientific axis uses one shared exponent in its axis name. Tick labels do
not mix `0` with independently formatted `× 10⁻⁴` strings.

## Verification

- Scientific suite: `50 PASS, 0 FAIL`.
- A6 unit tests: shared exponent, zero policy, area/bar/compare behavior.
- A1-A4 strict Mock browser regression: `PASS`.
- A1-A4 + A6 + A8 real PFC3D browser regression: `PASS`.
- Real PFC3D SVG export: 10 unique files with matching titles and roots.
- No new PFC solve was started.

## Evidence

```text
C:\Users\L\.codex\visualizations\2026\11\16\01a1e448-7bfd-7923-ad01-b03e22dea4fe\a6-real-pfc3d
C:\Users\L\.codex\visualizations\2026\11\16\01a1e448-7bfd-7923-ad01-b03e22dea4fe\a6-browser-final
C:\Users\L\.codex\visualizations\2026\11\16\01a1e448-7bfd-7923-ad01-b03e22dea4fe\a6-a1-a4-mock-browser
```

## Next stage

A5 may now begin. A9/A7 remain `NOT_VERIFIED`.
