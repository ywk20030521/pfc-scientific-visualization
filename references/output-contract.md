# Analysis Output Contract

Analysis output is separate from the standardized input contract:

```text
AnalysisResult/
|-- 03_analysis/
|-- 04_viewer/
|-- 05_charts/
|-- 06_publication_figures/
|-- 07_metadata/
`-- report/
```

There are intentionally no `01_raw_data/` or `02_standardized_data/`
directories. Those are owned and delivered by `pfc-headless`.

## Mandatory content

1. **Analysis**: supportable motion, spatial, contact, fracture, History,
   comparison, correlation and statistical results. Every derived value carries
   formula and lineage.
2. **Viewer**: offline local Three.js/ECharts bundle with a small HTML shell,
   separate local dependencies, real-frame chunks, on-demand Ball histories,
   unified interaction state, Case switching and property coloring.
3. **Charts**: physically justified, data-driven chart specifications with
   scores, alternatives and rejection reasons.
4. **Publication figures**: high-resolution PNG where rendered; vector SVG/PDF
   composition plan or result where supplied.
5. **Report**: experiment identity from the standardized contract, analysis
   channels, files, missing data, generated outputs, unsupported capabilities
   and verification status.

Additional metadata:

- `03_analysis/data_layers.json`: external standardized parent plus local
  ANALYSIS/DISPLAY lineage.
- `03_analysis/chart_decisions.json`: selected and rejected chart decisions.
- `03_analysis/display_data.json`: formatting and conversion metadata.
- `07_metadata/source_contract.json`: manifest hash, experiment hash, Case array
  hashes and read-only consumer policy.
- `07_metadata/experiment_capabilities.json`: per-Case analysis support.
- `07_metadata/output_contract.json`: generated, missing, unsupported and
  unverified items.

## Input and output ownership

- The standardized input root is read-only.
- Analysis cannot write inside the input root.
- The output root cannot equal, contain or be contained by the input root.
- `source_contract.json` records the verified parent identity.
- A changed source manifest requires a new analysis output root.

## Dynamic generation

The directory list is organizational, not a promise that every result exists:

- no crack channel -> no crack evolution chart;
- no contact endpoints/forces -> no contact-network visualization;
- fewer than two positions for an ID -> no trajectory;
- incomplete stress/strain inputs -> no stress–strain curve.

## Required status distinction

- `GENERATED`: actual artifact exists.
- `NOT_GENERATED`: artifact does not exist.
- `NOT_CAPTURED`: standardized source did not contain the field or entity.
- `NOT_SUPPORTED`: analysis/visual implementation cannot produce it.
- `INVALID`: integrity or physical validity failed.
- `NOT_VERIFIED`: exists but has not been acceptance-tested.

The output manifest lists actual files and hashes. It must not turn this
contract into a claim of completion.

PDF publication export requires a local vector converter on the composed SVG.
When no converter is supplied, report `NOT_SUPPORTED`.

## Visual acceptance gate

- Preserve the Nature palette and the light-only Viewer layout: golden-ratio
  render:chart split, collapsed bottom control dock, chart-only right rail.
  Hue semantics stay constant in the single light theme.
- Maintain consistent color semantics across scene and charts.
- Preserve true dimensions and sampled states.
- Use instancing and resource cleanup.
- Support fixed-view high-resolution PNG and vector chart export.
- Use a continuous particle color scale; the default robust display range is
  the current frame's P05–P95 with the interval shown in the legend.
- Keep page structure below 5 MiB excluding local dependencies and data files.
- Do not claim hardware GPU performance from software-WebGL automation.
- Keep fonts, axis rules, legends, units and labels consistent.
- Remain offline and disclose missing or unverified items.
