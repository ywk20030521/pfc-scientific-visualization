# Nature Visual Design System

The palette is inherited from the existing Viewer and is mandatory across scene,
charts and publication layout.

| Semantic use | Color |
|---|---|
| Primary / stress / main information | `#3C5488` |
| Fracture / shear / failure evolution | `#E64B35` |
| Blue-gray auxiliary | `#8491B4` |
| Tan auxiliary | `#B09C85` |
| Accent | `#F39B7F` |
| Particle ramp low | `#EAEEF5` |
| Particle ramp high | `#3C5488` |

Tension cracks use primary navy in the preserved Viewer convention; shear cracks
use vermilion. This semantic mapping must not change between charts and scene.

## Typography and layout

- Font: Arial/Helvetica with local Chinese fallback.
- Light-only theme (`themes.light.scene_background`) since 2026-11-23; the dark
  theme, theme toggle and `?theme=dark` path were removed. All colors are defined
  centrally in `assets/styles/scientific-visual-semantics.json`. The default
  Nature ramp is bright; the high-contrast ramp is optional.
- Thin dark axes; no dense grid lines by default.
- Panel captions use bold lowercase `(a)`, `(b)`, `(c)`.
- Align panels and preserve generous white space.
- Color bars and legends include variable name and unit.
- Do not add decorative gradients, shadows, 3D bevels or ornamental patterns.

## Semantic chart rules

- Continuous physical quantities use continuous scales.
- Continuous particle scales must remain legible when the distribution has a
  long tail. The default robust display interval is current-frame P05–P95; the
  legend states the actual values and the transform.
- Categories use discrete colors.
- Directional data preserves angular meaning.
- Multi-Case charts keep one scale and color meaning per variable.
- A radar chart must not normalize incompatible variables to create visual area
  advantages; the safe default is not to generate one.
- Missing values are shown as missing/unsupported, never as the ramp minimum.

## Number display

- Axis labels use one consistent notation and scale per axis.
- Very small or very large values switch to scientific notation such as
  `1.235 × 10⁻⁷`.
- Tooltips may show more significant digits than axes.
- Display strings never replace analysis values.

## Composition

- Odd counts use weighted primary/supporting layouts rather than blank filler.
- Even counts choose row/column orientation from page aspect.
- Direct comparisons use equal panel sizes; a scene may be primary.
- Panel gaps reserve space for labels, axes and legends.

The complete layout policy is in [figure-composition.md](figure-composition.md).
