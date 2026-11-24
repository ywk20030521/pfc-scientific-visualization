# Three.js Scientific Rendering

The scientific Viewer uses the minimalist Nature-style shell and consumes
only the verified standardized contract. It is **light-only** since 2026-11-23:
the dark theme, theme toggle and `?theme=dark` path were removed. All theme
colors come from `assets/styles/scientific-visual-semantics.json` under
`themes.light`. A bright Nature ramp is the default; a high-contrast ramp is
optional and selected in the bottom control dock.

## Scene

- The scene background uses `themes.light.scene_background`. Publication PNG
  export uses white or transparent background for journal-convention output.
- sRGB output with ACES filmic tone mapping (exposure 1.06) for the scene;
  quantitative particle instance colors opt out of tone mapping so the data
  mapping is preserved.
- Hemisphere, key, fill and cool rim lights, plus a small local equirectangular
  Canvas environment map, light a `MeshPhysicalMaterial` particle preset.
- PFC2D defaults to an orthographic view; PFC3D defaults to perspective.
- Axes, bounds, reset camera, orthographic/perspective switch and fixed-view
  capture are user controls.
- A display transform never changes stored physical coordinates.
- `assets/styles/scientific-visual-semantics.json` is the versioned visual
  contract. The builder injects it locally as `viewer/visual-semantics.js`.
- PFC2D particles use `CircleGeometry`; PFC3D particles use level-of-detail
  `SphereGeometry` (18×12 / 12×8 / 10×7 by ball count). Both use a shared
  `MeshPhysicalMaterial` preset with clearcoat and environment reflection.
- Quantitative colors are written to `instanceColor` as linear values and are
  not tone mapped. Renderer output remains sRGB and physical arrays are not
  transformed by the lighting model.
- The key directional light uses a controlled PCF soft shadow map. PFC3D
  particles cast and receive shadows to establish spatial depth without a
  synthetic physical floor.
- View presets include fit, isometric, front, top and side. PFC2D defaults to a
  top orthographic view; PFC3D defaults to a perspective isometric view.
- Fit mode frames the real Ball bounding volume, not the larger domain box. The
  domain box is an optional overlay and is hidden by default.

## Entities

- Balls are one `InstancedMesh`; transforms and colors are updated in place.
- PFC3D uses one reusable `SphereGeometry` with LOD chosen from the largest
  Case ball count.
- Per-frame ID sets determine visible instances. Removed Balls are hidden.
- Added Balls use their first real captured radius/position.
- Wall geometry updates in place when all vertices exist: each captured wall
  segment is drawn as an instanced semi-transparent solid rod, with an outline
  and vertex points. Absent geometry is hidden rather than guessed; true wall
  facets still require upstream triangle/normal data.
- Fracture line placement uses captured position, normal, diameter and event
  Cycle.
- Particle color is a continuous metric ramp. The default display transform uses
  the current frame's P05–P95 interval, shows that real interval in the legend,
  and saturates values outside it instead of letting an extreme outlier flatten
  the whole scene.
- Contact and Bond network rendering is enabled only when same-frame endpoint ID
  arrays exist. Optional force magnitudes color the lines. The preserved
  baseline has none.

## Performance

The implementation reuses `CircleGeometry` for PFC2D or `SphereGeometry` for
PFC3D, instance matrices, color buffers, Wall geometry, and chart instances.
Frame arrays are loaded in eight-frame
chunks with a five-chunk LRU. Ball histories live in separate sharded artifacts
and are loaded only for selected IDs. Case switching disposes chart objects and
clears trajectories, swaps that Case's independent static Ball ID/radius set,
and keeps instance capacity at the largest Case size. Time indicators are DOM overlays over ECharts SVG charts,
so playback does not rebuild chart options on every frame.

## Trajectory

Selecting a Ball ID searches actual selected frames. The polyline connects only
observed positions and reports start/end Cycle. Fewer than two samples yields
`INSUFFICIENT_REAL_SAMPLES`.

## Publication export

`window.PFCViewer.exportPNG()` renders the current camera at a requested width
with white or transparent background. `window.PFCViewer.exportFramePNG(frame,
width)` selects a real frame before rendering. `exportChartSVGs()` downloads
ECharts SVG panels and `exportCompositePanels()` composes a high-resolution PNG
panel sheet.

## Entity capability boundary

Scene controls are enabled only for entities present in the payload. Contact and
Bond controls appear only when endpoint arrays are captured and otherwise stay
hidden. Connections are never inferred from proximity or aggregate Wall force.
