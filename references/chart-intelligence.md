# Chart Intelligence Engine

`scripts/analysis/intelligence.py` selects charts from evidence. The legacy
`select_charts` function remains as a compatibility wrapper.

## Decision sequence

1. Confirm the channel or derived result exists.
2. Reject non-finite, invalid or physically uninterpretable data. A finite but
   constant channel is also rejected when the chart exists to show trend,
   relationship or variation.
3. Resolve physical meaning from declared channel metadata.
4. Identify time, Cycle, spatial, Case and variable dimensions.
5. Count finite and missing observations.
6. Determine the analysis goal.
7. Generate compatible candidates.
8. Score expression value.
9. Exclude misleading or duplicate candidates.
10. Emit the chart and decision record, or a rejection record.

## Supported families

| Structure | Candidate families |
|---|---|
| Ordered time/Cycle response | line, area, dual-line |
| Two continuous variables | scatter, line path |
| Particle XY distribution | heatmap or scatter when supportable |
| Distribution sample | histogram, boxplot |
| Category/final summary | bar, grouped bar, stacked bar |
| Fracture direction | rose or polar |
| Several aligned varying channels | correlation heatmap |
| Several comparable normalized indices | radar only when units and meaning permit |

Support in the type registry does not imply that every dataset should generate
that type.

## Decision record

Each spec includes:

- `source_channels`;
- `analysis_goal`;
- `decision.score`;
- `decision.reason`;
- `decision.alternatives`;
- `decision.derived`;
- `decision.missing_count`;
- `decision.manual_override`;
- `display` formatting metadata;
- unit conversion records where scaling occurred.

Rejected candidates are written to `03_analysis/chart_decisions.json` with
`NOT_CAPTURED`, `NOT_GENERATED`, `INVALID` or `NOT_SUPPORTED` as applicable.
Constant stress, strain, load, speed or motion channels are explicitly recorded
as non-informative and do not create flat placeholder charts.

## Manual override

Use a JSON object keyed by chart ID:

```json
{
  "charts": {
    "case_0:stress_strain": {
      "type": "scatter",
      "options": {
        "show_symbol": true,
        "symbol_size": 4
      }
    }
  }
}
```

Pass it with `run_pipeline.py --chart-overrides <file>`. An override is applied
only when the requested type matches the chart's compatible data structure.
