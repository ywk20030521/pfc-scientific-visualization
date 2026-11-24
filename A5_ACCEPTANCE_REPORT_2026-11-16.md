# A5 Acceptance Report

## Decision

A5 is `PASS` for this stage. A1-A4 remained frozen and passed the strict Mock
regression after robust histograms were introduced.

## Implemented binning contract

Analysis and current-frame Viewer distributions use:

```text
ROBUST_P05_P95_WITH_OVERFLOW
```

- P05-P95 is the continuous interior interval.
- Values below P05 use an explicit `< P05` underflow bin.
- Values above P95 use an explicit `> P95` overflow bin.
- Missing/non-finite values are counted separately and never assigned to a bin.
- Every finite observation is assigned exactly once.

The histogram record includes total, finite and missing counts, interior
quantiles, observed extrema, underflow/overflow counts, bin records and labels.
No extreme value is removed.

The Viewer current-frame brush and click interactions use explicit bin ranges;
tail bins map to their real lower/upper ranges.

## Real PFC3D evidence

Case 22 final-frame displacement:

```text
finite count: 2296
P05-P95 interior: 0.0000835702 ... 0.0003858370 m
underflow bin: 115
32 interior bins
overflow bin: 115
count sum: 2296
```

The live final-frame histogram produced the same structural result:

- `ROBUST_P05_P95_WITH_OVERFLOW`;
- 2,296 finite observations;
- 115 underflow and 115 overflow observations;
- count sum 2,296;
- explicit `< P05` and `> P95` labels.

The live interval differs only at floating-point payload precision.

## Verification

- Scientific suite: `53 PASS, 0 FAIL`.
- A5 tests cover extreme tails, preservation of all finite observations,
  missing counts and chart propagation.
- A1-A4 strict Mock browser regression: `PASS`.
- A1-A4 + A5-A8 real PFC3D browser regression: `PASS`.
- Real PFC3D SVG export: 10 unique files with matching titles and roots.
- No new PFC solve was started.

## Evidence

```text
C:\Users\L\.codex\visualizations\2026\11\16\01a1e448-7bfd-7923-ad01-b03e22dea4fe\a5-real-pfc3d
C:\Users\L\.codex\visualizations\2026\11\16\01a1e448-7bfd-7923-ad01-b03e22dea4fe\a5-browser
C:\Users\L\.codex\visualizations\2026\11\16\01a1e448-7bfd-7923-ad01-b03e22dea4fe\a5-a1-a4-mock-browser
```

## Next stage

A9 identity mapping and A7 publication presentation may now begin as the final
joint stage.
