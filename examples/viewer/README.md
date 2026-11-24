# Viewer Examples

## Primary real-data reference case

`../reference_3d_case/confined_break_6k/` is the primary reference case for the
skill. It is a complete PFC3D case, not a standalone `case.json`: it contains the
raw PFC run, the immutable standardized delivery, and the full viewer/analysis
output.

Run ID: `run_case17_confined_break_6k_r1`

- 6379 real balls, six finite walls, 19 real frames
- 3721 real FISH bond-break events with endpoint Ball IDs
- data contract `PASS`, viewer payload `PASS`, browser no pageerror
- open `../reference_3d_case/confined_break_6k/README.md` for evidence and limits

The former mock showcase has been removed and replaced by this complete real
3D case. `build_mock_showcase.py` remains as a utility if a synthetic layout
regression fixture is ever needed, but its output is not the primary reference.

## Full-capability regression dataset

`../build_fullcapability_mock.py` generates `standardized_data/FullCapability_Mock/`,
a MOCK contract that exercises every Viewer channel. It uses the real headless
converter field names plus explicitly labeled MOCK extensions to test bond
rendering and dynamic cracks. Rebuild and run the kernel with:

```bash
python examples/build_fullcapability_mock.py
PYTHONPATH=scripts python scripts/run_pipeline.py \
  --input examples/standardized_data/FullCapability_Mock \
  --output <AnalysisResult> --title "PFC-SV Full-Capability Mock"
```

Note: real headless deliveries now emit fracture endpoint Ball IDs and wall
face facets after the 2026-11-23 patches; see the primary real-data reference
case above. A standalone bond array remains `NOT_CAPTURED`. The mock still
exercises the full-capability Viewer path and is kept as a regression fixture.

## Other data example

`../standardized_data/Mock_Experiment/` is the small 4-frame data-contract
example. It is unchanged and still runs through `run_pipeline.py`.
