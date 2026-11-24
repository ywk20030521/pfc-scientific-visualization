# ECharts Intelligent Chart System

The fixed `stressChart`/`responseChart` pair is replaced in the scientific
Viewer by data-driven chart specifications. The legacy Viewer remains untouched.

## Selector decisions

| Data condition | Preferred chart |
|---|---|
| Stress + strain | Line, stress–strain path |
| Mechanical time + stress | Line |
| Frame motion + cumulative cracks | Dual-axis line |
| Final particle displacement distribution | Histogram |
| Fracture azimuth | Rose/polar plot |
| Final XY particle count | Heatmap; labeled as count density |
| Multiple temporal channels | Correlation heatmap |
| Multiple Cases | Native/final bar comparison with common semantics |

The implementation also supports scatter, area, stacked bar, boxplot, radar and
generic polar options for future channels when their data and meanings support
them.

## Constraints

- Do not generate every supported type for completeness.
- Do not create a stress chart unless stress is physically derived.
- Do not draw a contact network from Wall aggregate force.
- Clicking a temporal chart must resolve to a real frame index.
- Dragging a temporal chart must update the same `ViewerState` used by the 3D
  scene and timeline.
- Temporal chart cursors are lightweight overlays; playback must not rebuild the
  complete ECharts option object for every frame.
- The Viewer uses one full-width chart column inside the side panel so axes,
  legends and labels are not compressed into narrow 320 px cells.
- Brushing the current-frame displacement or speed distribution highlights the
  matching particles in the 3D scene without reloading the experiment.
- Case switching updates chart data and releases prior ECharts instances.
- Chart titles state the physical meaning, not merely the chart type.
- Every selected chart carries source channels, a rationale, alternative types,
  missing-data count and display formatting metadata.
- Axes use the auto scientific/decimal formatting declared in the chart spec;
  tooltips use a higher-precision formatter.
- Manual chart type overrides are accepted only for compatible data shapes.

## Export

Charts use the SVG renderer. The Viewer downloads SVG panels; the Python
publication composer layouts existing SVGs into a white multi-panel vector
figure. It can also embed the Viewer's high-resolution scene PNG as the first
panel while keeping charts as vectors. If no scene or exported panel exists,
the result is `NOT_GENERATED`.

Individual SVG exports include the chart title. The Viewer composite PNG adds
panel letters, titles and source status and uses the adaptive odd/even layout.

See [chart-intelligence.md](chart-intelligence.md) and
[figure-composition.md](figure-composition.md).
