# Verification and Unsupported Items

## Verified in the maintenance run

| Item | Status |
|---|---|
| Split scientific Mock/unit/static suite | `PASS`, 61 tests |
| Split pfc-headless capture/standardization suite | `PASS`, 25 tests |
| Standardized-contract separation and tamper rejection | `PASS` |
| Real PFC3D frame payload generation | `PASS` in earlier integrated build |
| Real PFC3D browser load/interactions and A1-A9 | `PASS`, 2026-11-16 |
| Real PFC2D browser load/interactions | `PASS` in earlier integrated build |
| Post-split real browser acceptance | `PASS` for A1-A9 |

The browser review used `verify_lazy_viewer.mjs` for the strict Mock scenario and
`verify_real_frame_contract.mjs` for a `REAL_PFC` PFC3D Case. Both used the real
download button rather than the internal SVG Data URL API. The final real case
also validates robust histogram tails, axis contracts, Case availability,
colorbar semantics, SVG clipping and embedded chart identity.

## Not verified in this environment

| Item | Status | Reason |
|---|---|---|
| New PFC2D/PFC3D solve execution | `NOT_EXECUTED` | No PFC process started during maintenance |
| PFC2D upgraded Viewer | `PASS` | Reviewed with the available real PFC2D capture |
| Hardware-GPU performance | `NOT_VERIFIED` | No benchmark run |
| Contact/Bond rendering with real data | `NOT_VERIFIED` | The reviewed case has no endpoint arrays |
| Clump membership rendering | `NOT_CAPTURED` | Reviewed baseline capture has no clump membership |
| PDF vector output | `NOT_SUPPORTED` | Requires a local vector converter |

## Intentional non-linkage

- 3D Ball to 2D projected marker.
- 3D crack to 2D projected crack.
- Camera-to-2D bidirectional synchronization.
- All charts bidirectionally linked to 3D without ID correspondence.

These remain recorded in `04_viewer/linkage_decisions.json`.
