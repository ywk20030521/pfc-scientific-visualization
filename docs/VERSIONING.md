# Versioning and release process

## Scheme

Use [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`, tag
prefix `v`.

- `MAJOR`: breaking change to the input contract, output contract or schema.
- `MINOR`: backward-compatible analysis, chart or Viewer capability.
- `PATCH`: bug fix, performance fix or documentation-only change.

Pre-release tags use `v2.1.0-rc.1` and must be marked as pre-release on GitHub.

## Current state

No Git tag exists. The historical `v2.1` ZIP is a package label only. The
proposed first tag is `v2.1.0`, **not created and blocked**; see
`docs/RELEASE_NOTES_DRAFT.md`.

## Release checklist

1. Close all P0 rows in `docs/OPEN_SOURCE_READINESS.md` on `main`.
2. Run `PYTHONPATH=scripts python -m unittest discover -s tests -p "test_*.py"`.
   If a fresh worktree fails on a hash check, re-run in the main workspace and
   resolve line-ending handling before proceeding.
3. Repeat browser/offline Viewer verification on a real standardized dataset;
   record real-data evidence separately.
4. Move `[Unreleased]` items in `CHANGELOG.md` into a dated version section.
5. Finalize `docs/RELEASE_NOTES_DRAFT.md` and review the capability/acceptance
   reports for consistency.
6. Create the tag from the verified commit, then the GitHub Release.

## Never

- Do not tag while a fresh-worktree acceptance test is red.
- Do not describe an offline local check as independent-machine or public
  deployment verification.
- Do not describe an analysis artifact as a Finding or as model validation.
