## Summary

<!-- What changes and why? Link the issue if there is one. -->

Closes #

## Type of change

- [ ] Bug fix
- [ ] New analysis / visualization capability inside this boundary
- [ ] Output contract change (additive)
- [ ] Output contract change (breaking — requires Headless/RE coordination)
- [ ] Documentation / repository configuration
- [ ] Test-only change

## Verification

Commands run and results:

```text
PYTHONPATH=scripts python -m unittest discover -s tests -p "test_*.py"
```

- [ ] Unit tests pass; count and any skips recorded
- [ ] Real PFC standardized data used and identified **if** claiming real-data evidence
- [ ] Browser / Viewer check recorded separately from unit tests
- [ ] Renderer performance, scientific fidelity and publication output reported separately
- [ ] No analysis result described as a scientific Finding or model validation

## Responsibility and data contract

- [ ] RAW data not modified; DERIVED objects have source references
- [ ] Canonical `RAW / STANDARDIZED / DERIVED` layers used
- [ ] Analysis feedback markers (`ANALYSIS_FEEDBACK_NOT_SCIENTIFIC_FINDING`) preserved
- [ ] Formula, algorithm version, units and input refs recorded for new outputs
- [ ] Status vocabulary follows `CONTRIBUTING.md`

## Documentation

- [ ] README / SKILL.md updated if behavior changed
- [ ] `CHANGELOG.md` entry added under `[Unreleased]`
- [ ] Acceptance or capability report updated when evidence changes
- [ ] Known limitations stated (offline vs deployed, memory vs ZIP size)

## Reviewer notes

<!-- Any cross-repository impact, rollback plan, or follow-up PR. -->
