# PR1-PR8 Scientific Visualization Upgrade

> Historical upstream view. Capture and standardization dependencies now cross
> the immutable `pfc.standardized-experiment@1.0.0` contract boundary.

The implementation is additive to the existing Console-only capture foundation.
No GUI path is introduced.

```text
Existing Console capture and standardization
  -> PR1 data schema + visual semantics
      -> PR2 units, formatting and display layer
          -> PR3 Chart Intelligence Engine
              -> PR4/4.1 Three.js scientific Viewer
                  -> PR5 ECharts + adaptive figure composition
                      -> PR6 PFC2D/3D capability adaptation
                          -> PR7 test code and coverage plan
                              -> PR8 integration, documentation and ZIP
```

| PR | Depends on | Static implementation evidence | Current verification |
|---|---|---|---|
| PR1 | Existing schema/capture | Layer builders, enriched channel metadata, visual token config, data-layer schema | `NOT_VERIFIED` |
| PR2 | PR1 | Unit registry, display formatter, conversion lineage | `NOT_VERIFIED` |
| PR3 | PR1-PR2 | Candidate generation, score/reason/alternatives, rejection log, override gate | `NOT_VERIFIED` |
| PR4 | PR3, existing Viewer | PFC2D circle/PFC3D sphere geometry, camera presets, metric/entity capability gates | `NOT_VERIFIED` |
| PR4.1 | PR4 | Local visual semantics, sRGB/no-tone-map color handling, instancing and export | `NOT_VERIFIED` |
| PR5 | PR3-PR4 | Scientific ECharts formatting and adaptive odd/even composition | `NOT_VERIFIED` |
| PR6 | PR1-PR5 | Per-Case capability inspection and safe mixed-Case handling | `NOT_VERIFIED` |
| PR7 | PR1-PR6 | Test code, coverage matrix and unverified-item inventory | `NOT_EXECUTED` |
| PR8 | PR1-PR7 | Integrated docs, output contract, Skill metadata and ZIP packaging | `GENERATED`, `NOT_VERIFIED` |

Artifact creation is not acceptance. The release report must keep
implementation, test execution, PFC validation, browser validation and
performance validation separate.
