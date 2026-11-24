# Performance and Publication Report

> Historical snapshot from an earlier Viewer build. No performance or export
> measurement was run for the current PR1-PR8 upgrade.

Measured PFC3D Viewer:

| Metric | Value |
|---|---:|
| HTML shell | 8,130 B |
| Ready time | 830 ms |
| Peak JS heap | 13.4 MB |
| Final JS heap | 13.4 MB |
| Median software-WebGL FPS | 17.9 |
| Playback test | 10 s |
| Maximum loaded chunks | 3 |
| Maximum draw calls | 4 |
| Maximum geometries | 4 |
| Runtime external requests | 0 |
| Chart SVG exports | 7 |

The page uses one reused instanced particle mesh, a bounded frame-chunk LRU,
on-demand Ball-history buckets, and reused ECharts instances. The page shell
is far below the 5 MiB target.

The FPS value comes from SwiftShader automation. It is not evidence of
hardware-GPU performance. No baseline artifact was supplied for this release,
so a before/after percentage is not claimed.

Publication outputs generated:

- `viewer_frame.png`
- `composite_panels.png`
- seven `chart_XX.svg`
- `figure_1.svg` with scene and vector panels composed by
  `scripts/charts/publication.py`
