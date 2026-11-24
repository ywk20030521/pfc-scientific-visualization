# Viewer State and Performance

## One state owner

The scientific Viewer has one `ViewerState`. Three.js, ECharts, controls,
timeline and selection panels subscribe to it.

```text
currentCase
currentFrame
currentCycle
currentTime
selectedBallIds[]       real PFC Ball IDs
selectedMetric          displacement | speed | acceleration
selectedRange           [low, high] | null
colorMetric
```

All controls dispatch actions to this store. No renderer keeps a competing
"current frame" value.

## Required linkage

- Timeline, Cycle lookup, playback, chart clicks and chart dragging switch the
  same real frame index.
- Hovering is not data selection. Click/drag/drag-brush actions are explicit.
- Clicking a 3D Ball adds its real ID to `selectedBallIds`; Shift/Ctrl toggles
  multi-selection.
- Selecting Ball IDs loads only the matching history buckets and draws only
  observed trajectory points. A Ball may be absent in some real frames; its
  history is then a strict subset of Viewer frames. Verification validates the
  source-frame / viewer-frame / Cycle mapping of every reported row and
  records the coverage, rather than inventing missing samples.
- Brushing a current-frame displacement or speed distribution sets
  `selectedRange`; the 3D scene highlights Balls whose current values fall in
  that range.
- Acceleration is available as a particle color metric when the analysis array
  exists. Unsupported metrics are disabled rather than shown as functional.
- Temporal charts map real Cycle/time values back to captured frame indices, so
  a derived series with a missing initial sample remains linkable.
- Case switching clears the frame, range and selected IDs before loading the new
  Case.

If a metric has no particle-level correspondence, it must remain
`NOT_SUPPORTED` for range linkage. Do not manufacture an ID mapping.

## Payload layout

```text
04_viewer/
|-- scientific_viewer.html       small page shell
|-- viewer/
|   |-- scientific-viewer.js
|   |-- scientific-viewer.css
|   `-- vendor/                  local Three.js, OrbitControls, ECharts
`-- data/
    |-- catalog.js
    |-- static.js
    `-- cases/case_N/
        |-- meta.js
        |-- charts.js
        |-- chunks/chunk_NNN.js
        `-- histories/bucket_NNN.js
```

The local `viewer/visual-semantics.js` carries the Three.js/ECharts token
contract. `04_viewer/linkage_decisions.json` records implemented and omitted
linkages.

Dynamic particle frames and selected-Ball histories are separate artifacts. The
payload builder reuses a chunk inside one file:// script tag so the generated
Viewer works without a web server.

## Loading and memory rules

- Keep every real frame by default (`--max-frames 0`). A positive limit is
  explicit sampling and must be disclosed.
- Load frame chunks in groups of eight.
- Keep at most five frame chunks in the browser LRU.
- Decode base64 once per loaded chunk, not once per render.
- Keep ECharts and Three.js instances alive across frame changes.
- Update time cursors with DOM overlays instead of rebuilding chart options.
- Reuse `InstancedMesh`, instance buffers, geometries, chart instances and
  canvas/renderer resources.
- Use vertices-only `CircleGeometry` in PFC2D and `SphereGeometry` in PFC3D.
- Disable unsupported particle metrics and entity layers from the Case
  capability metadata instead of presenting empty controls as functional.
- Composite export processes every data-driven chart, uses an odd/even adaptive
  layout, and writes panel number, title and source status into the raster.
- Dispose charts and GPU resources on Case switching or page exit where
  applicable.

## Benchmark contract

Record:

- HTML shell size;
- payload size;
- first ready time;
- first real-frame time;
- median playback FPS;
- peak JS heap;
- JS heap after playback;
- loaded chunk maximum;
- draw calls and geometry count.

`scripts/benchmark_viewer.mjs` records browser-automation measurements. Headless
SwiftShader FPS is a relative diagnostic and must not be described as hardware
GPU performance.

## Rebuild policy

`scripts/build_scientific_viewer.py` hashes source-file metadata into a payload
signature. A CSS/layout/chart-template change reuses the existing payload.
`--rebuild-payload` is required after standardized or analysis arrays change.
PFC is never started by either path.
