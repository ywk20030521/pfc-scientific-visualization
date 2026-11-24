# 2D/3D Linkage Decisions

Shared state does not imply that every view must be linked. The Viewer shares
`currentCase`, `currentFrame`, `currentCycle` and `currentTime`.

## Implemented

| Feature | Scope |
|---|---|
| Timeline synchronization | Playback, timeline, Cycle lookup, temporal charts and history cursors |
| Case synchronization | Case switch resets frame, range and Ball selection |
| Particle selection/history | Real Ball ID to on-demand displacement/speed history |
| Distribution range to scene | Current-frame histogram brush highlights matching Balls |

## Intentionally not implemented

| Feature | Reason |
|---|---|
| 3D Ball to a 2D projected marker | Aggregate distribution view already answers the current spatial question; projection adds synchronization cost without new evidence |
| 3D crack to 2D projected crack | Direction is represented by rose charts and crack lines; a useful renderer requires an explicit shared slice |
| Camera to 2D view synchronization | Camera rotation is exploratory, not physical state |
| All charts bidirectional with 3D | Aggregate charts often have no particle-level ID correspondence |
| Contact renderer in the default baseline | Contact endpoints are not captured; aggregate Wall force is not a network |

`04_viewer/linkage_decisions.json` records scientific need, interaction value,
technical/coordinate/data complexity, performance cost, maintenance cost,
decision and reason. A capability that lacks correspondence remains
`NOT_SUPPORTED` rather than creating a plausible-looking fake link.
