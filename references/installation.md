# Installation

## Install as a Codex Skill

Copy the complete `pfc-scientific-visualization/` directory into the Codex
skills directory:

```text
$CODEX_HOME/skills/pfc-scientific-visualization/
```

When `CODEX_HOME` is unset, use `~/.codex/skills/`. Keep the whole directory;
the Viewer depends on `assets/vendor`.

## Runtime dependencies

- A read-only standardized experiment contract from `pfc-headless`.
- Python with NumPy for scientific analysis and payload generation.
- No npm installation is required for generated Viewers.
- No network access is required by the Viewer.
- PFC, the Console build and `itasca-mcp-bridge` are not required by this Skill.

## Offline assets

Required local files:

```text
assets/vendor/three.min.js
assets/vendor/OrbitControls.js
assets/vendor/echarts.min.js
```

The builder copies them into `04_viewer/viewer/vendor/`. The generated page is
offline but is a directory bundle: `scientific_viewer.html`, `viewer/` and
`data/` must stay together. A missing vendor or chunk file is an error; it is
not replaced from a CDN.

The builder also writes `viewer/visual-semantics.js` from the versioned
`assets/styles/scientific-visual-semantics.json` file. It remains local and
offline.

## Recommended directory layout

Keep standardized contracts and analysis outputs outside the Skill directory.
Use a new `--output` directory for every analysis run so the input contract
remains immutable.

## Verification boundary

Installation is separate from execution acceptance. A new workstation must
verify its standardized contract and run browser/export checks before the
analysis capability matrix can be marked verified.
