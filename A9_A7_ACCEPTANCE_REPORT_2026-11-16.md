# A9 + A7 Acceptance Report

## Decision

A9 identity mapping and A7 publication presentation are `PASS` for this joint
stage. A1-A4 remained frozen and passed both strict Mock and real PFC3D
regressions after the changes.

## A9 identity and compatibility

### Legacy temporal charts

- A legacy temporal chart is sliced only when it has no `source_indices`, its
  x-axis is time/Cycle, and every temporal data array spans the complete source
  frame count.
- This compatibility path is labeled
  `LEGACY_EXACT_FULL_SOURCE_EXTENT`.
- Ambiguous or truncated legacy temporal arrays are rejected instead of being
  assigned by array position.
- Non-temporal legacy artifacts are labeled
  `NOT_REQUIRED_NON_TEMPORAL_CHART`.

### SVG identity

Each exported chart SVG now carries:

- `data-pfc-chart-id`;
- `data-pfc-case-id`;
- `data-pfc-title`.

The download filename and A1-A4 download scheduling are unchanged.

The composer now:

- uses natural numeric file ordering;
- requires an embedded chart ID or a unique embedded title;
- rejects unresolved identity instead of guessing by file position;
- reports each identity resolution method.

The real Case 22 composition resolved all six panels by
`EMBEDDED_CHART_ID`:

```text
case_22:speed_time
case_22:acceleration_time
case_22:motion
case_22:displacement_hist
case_22:particle_density
case_22:correlation
```

### Publication selection

The previous 129-panel single plan is replaced by Case-aware publication
planning:

```text
analysis charts:       129
selected for figures:  125
omitted from figures:    4
figure groups:          24
maximum panels/figure:   6
```

All analysis charts remain present. Only the publication plan selects the
highest-value charts per Case.

Panel labels now use stable alphabetic notation and continue `aa`, `ab`, etc.
after `z`.

## A7 publication presentation

- Heatmap colorbar states `颗粒数（高）` / `0`.
- Correlation colorbar states `Pearson r +1` / `Pearson r −1`.
- Category-axis names use centered `middle` placement instead of default end
  placement.
- Grid `containLabel` is enabled for chart groups.
- Long titles wrap instead of shrinking font.
- The composer removes the embedded single-chart title group when an outer
  panel title is present, preventing duplicate titles.

## Real Case 22 figure

```text
layout: 2 × 3
panels: (a), (b), (c), (d), (e), (f)
outside-root text: none
duplicate panel titles: none
identity resolution failures: none
```

Visual inspection confirms:

- all panel titles are visible once;
- axes and colorbars remain inside panels;
- the robust histogram has explicit `< P05` / `> P95` bins;
- the correlation colorbar names Pearson `r`;
- all six panels use their matching chart specs.

## Verification

- Scientific suite: `61 PASS, 0 FAIL`.
- A1-A4 strict Mock browser regression: `PASS`.
- A1-A4 + A5-A9 real PFC3D browser regression: `PASS`.
- Real SVG button download: 10 unique files; identity metadata and titles
  matched.
- Composed Case 22 SVG: 6 panels, vector, no clipping, no duplicate titles.
- No new PFC solve was started.

## Evidence

```text
C:\Users\L\.codex\visualizations\2026\11\16\01a1e448-7bfd-7923-ad01-b03e22dea4fe\a5-a9-final
C:\Users\L\.codex\visualizations\2026\11\16\01a1e448-7bfd-7923-ad01-b03e22dea4fe\a5-a9-final-browser
C:\Users\L\.codex\visualizations\2026\11\16\01a1e448-7bfd-7923-ad01-b03e22dea4fe\a5-a9-final-compose
C:\Users\L\.codex\visualizations\2026\11\16\01a1e448-7bfd-7923-ad01-b03e22dea4fe\a5-a9-final-mock-browser
```

Final composed PNG:

```text
C:\Users\L\.codex\visualizations\2026\11\16\01a1e448-7bfd-7923-ad01-b03e22dea4fe\a5-a9-final-compose\case_22_composed.png
```

## Remaining limits

- A10-A15 are outside this round.
- No new PFC2D/PFC3D solve was executed.
- Hardware-GPU performance was not re-benchmarked.
- PDF conversion remains dependent on an external local vector converter.
