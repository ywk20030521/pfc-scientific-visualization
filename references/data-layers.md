# External Raw, Analysis and Display Data

The standardized experiment from `pfc-headless` is the immutable external raw
parent. This Skill writes only `ANALYSIS_DATA` and `DISPLAY_DATA`; their
machine-readable records live in `scripts/schema/layers.py`.

## RAW_DATA

Raw data is captured, quality-checked and standardized by `pfc-headless`.

- Precision and source units are retained.
- The standardized root and raw evidence are never rewritten by this Skill.
- Artifact SHA-256 and size are recorded when available.
- Case, Frame, Cycle, mechanical time and capture source remain linkable
  through the external contract.
- An unknown hash is `null`; it is not invented.

## ANALYSIS_DATA

Analysis data contains supportable statistics, spatial transforms, unit
conversions, aggregates, distributions, comparisons or derivations.

It references the pfc-headless delivery manifest as its external parent.

Every operation records:

- method/formula;
- input channel or array identity;
- parameters;
- output field and unit;
- source class;
- applicability and version.

An unfamiliar field is not promoted to stress, strain or force by name.

## DISPLAY_DATA

Display data prepares values for charts and figures:

- automatic scientific or decimal notation;
- significant digits and decimal places;
- axis and legend formatting;
- single-scale unit display;
- higher-precision tooltip values;
- missing-value text.

`scripts/analysis/formatting.py` implements this boundary.
`scripts/analysis/units.py` performs reversible conversions for known unit
dimensions. A display value never replaces the numerical analysis array.

`03_analysis/display_data.json` stores the formatting rules and conversions.
Per-point display strings are derived on render so large datasets are not
duplicated in the package.

## Lineage invariant

```text
RAW_DATA
  [owned by pfc-headless, immutable external contract]
  -> ANALYSIS_DATA
  [owned by pfc-scientific-visualization]
  -> DISPLAY_DATA
  [owned by pfc-scientific-visualization]
```

Analysis may depend on another analysis record when its inputs are explicit.
Display records reference the local analysis layer and formatting method. The
pipeline writes the normalized inventory to `03_analysis/data_layers.json`.
