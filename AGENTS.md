# Contributor guidance

## Contract and scope

- Read `docs/GENERATOR.md` before behavioral changes. Explicit user requirements override its illustrative examples: lognormal distributions require positive sigma, and this project is standalone Python.
- Keep canonical episodes separate from evaluator annotations. Never add oracle IDs, confidence, provenance, incident templates, or generation parameters to episode fields or labels.
- Do not import production analyzer code, change production grouping, contact live systems, or use production data or credentials.
- Keep the core independent of Prometheus. Any future exporter belongs in a separate adapter.

## Implementation conventions

- Use Python's standard library; PyYAML is the only runtime dependency. Use `yaml.SafeLoader` with explicit duplicate-key, alias, field, and type validation.
- Keep functions direct and small; do not add service layers, plugin systems, or speculative configuration.
- Derive random streams from stable, unambiguous identifiers and the root seed. Never use Python's process-randomized `hash()`, wall-clock timestamps, or unordered iteration for output.
- Preserve deterministic serialization, input/output separation, and existing dataset directories. Stage complete output before publication and clean up only temporary paths owned by the current operation.
- Reject unsupported fields and profiles with file/field errors; do not approximate them silently. Document rounding and any intentional modeling limits.
- Update the README and focused regression tests when changing the public YAML contract or CLI. New dependencies, configuration changes, and wider work require scoped approval.

## Verification

Run from the project root with the existing Python/PyYAML environment; do not install dependencies implicitly.

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q generator tests
python3 -m generator validate --scenario examples/01-delayed-symptoms/scenario.yaml

# Run these when already installed; never install them implicitly:
ruff check --no-cache generator tests
ruff format --no-cache --check generator tests
mypy --no-incremental --cache-dir=/dev/null --check-untyped-defs generator tests
```

The unittest command is the full suite; run it when requested or approved. For narrower changes use a selected test with `PYTHONPATH=tests python3 -m unittest test_generator.GeneratorTests.test_name`.

Tests must check generator contracts, not production grouping decisions. Include byte-for-byte repeatability of all four artifacts and the intended properties of the example scenarios. Run CLI generation into a new temporary output path, never over an existing dataset. Report unavailable checks honestly; compilation is not a lint or type check.
