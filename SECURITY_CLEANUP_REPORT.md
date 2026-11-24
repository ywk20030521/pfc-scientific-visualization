# Security and Cleanup Report

- GUI execution scripts were removed from the installable Skill.
- Engine discovery accepts only `pfc2d9_console.exe` or
  `pfc3d9_console.exe`.
- Bridge endpoints are restricted to loopback in `BridgeClient`.
- Runtime state stores a validated PID; stop never targets every PFC process by
  executable name.
- Cleanup is dry-run by default.
- Apply requires the exact token `CLEAN_INTERMEDIATE`.
- Protected directories: raw, standardized, analysis, Viewer, charts,
  publication figures, metadata, report.
- Protected suffixes include `.sav`, `.prj`, `.dat`, `.fis`, `.his`, `.p2dat`
  and `.p3dat`.
- Live cleanup plans for the PFC2D and PFC3D result packages had zero candidate
  deletions, so historical evidence was retained.
- Failed acceptance runs remain in `.console-runtime/acceptance/` as evidence
  and are not overwritten.
