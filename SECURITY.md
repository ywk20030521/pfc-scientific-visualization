# Security Policy

## Supported versions

| Version | Status |
|---|---|
| `main` | Development baseline; security fixes are applied here first. |
| Published tags | Receive fixes only when a maintenance release is cut. |

No tag has been published yet. The proposed first tag and its blockers are in
`docs/RELEASE_NOTES_DRAFT.md`.

## Reporting a vulnerability

Please **do not** open a public issue for an exploitable defect. Use GitHub's
private vulnerability reporting for this repository (`Security` →
`Report a vulnerability`), or contact maintainers privately through the
account listed in the repository profile.

Include:

- affected version or commit;
- smallest non-proprietary dataset that reproduces the issue;
- impact (for example: an output schema that makes a downstream Skill accept
  unverified data as a scientific finding);
- whether public disclosure already occurred.

You should receive an acknowledgement within a few working days. We will
coordinate disclosure and credit after a fix is available.

## Security- and integrity-relevant boundaries

- RAW data is never modified in place; corrections create DERIVED objects.
- Analysis feedback must carry
  `ANALYSIS_FEEDBACK_NOT_SCIENTIFIC_FINDING` / `NOT_RE_FINDING` markers.
- Data layers use canonical `RAW / STANDARDIZED / DERIVED` values with an
  explicit legacy mapping.
- A chart or Viewer artifact is never evidence of scientific validity.
- Offline Viewer verification must distinguish local `file://` checks from
  public deployment.
