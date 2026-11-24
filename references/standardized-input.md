# Standardized Input Contract

## Source

The only supported experiment input is:

```text
pfc.standardized-experiment@1.0.0
```

It is produced by `pfc-headless`. A raw capture directory is not a valid input
to this Skill.

## Required files

```text
<StandardizedExperiment>/
|-- delivery_manifest.json
|-- experiment.json
|-- conversion_report.json
|-- schema/
|   |-- experiment.schema.json
|   |-- case.schema.json
|   |-- channel.schema.json
|   `-- frame.schema.json
`-- cases/
    `-- case_N/
        |-- arrays.npz
        |-- case.json
        |-- channels.json
        |-- frames.json
        |-- events.json
        |-- entity_changes.json
        |-- frame_summary.csv
        `-- conversion_report.json
```

## Verification before analysis

`scripts/standard_contract.py` checks:

- contract name and version;
- immutable and read-only declarations;
- experiment hash;
- every manifest artifact size and SHA-256;
- Case membership and arrays hash;
- core NPZ keys and frame-offset lengths.

Any failure stops the pipeline. The consumer never patches hashes, inserts
missing arrays, replaces missing values with zeros or transforms the input in
place.

## Ownership

The standardized root is owned by `pfc-headless`. This Skill only reads it and
records:

- absolute source-root path;
- delivery-manifest SHA-256;
- experiment SHA-256;
- Case array hashes;
- contract name and version.

These references are written to `07_metadata/source_contract.json` and
`03_analysis/data_layers.json`.

## Output separation

The analysis output root must not:

- equal the standardized input root;
- be a parent of the standardized input root;
- be a descendant of the standardized input root.

The analysis package writes only `03_analysis/`, `04_viewer/`, `05_charts/`,
`06_publication_figures/`, `07_metadata/` and `report/`.

## Reproducibility

Re-run analysis from the same immutable contract to compare analysis outputs.
If the manifest hash differs, treat it as a new experiment revision and create
a new analysis output directory.
