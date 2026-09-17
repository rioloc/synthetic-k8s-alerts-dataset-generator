# Synthetic alert-dataset generator

A small, standalone **Python** CLI for generating deterministic benchmark input for incident-grouping algorithms. The design contract is [`docs/GENERATOR.md`](docs/GENERATOR.md); this README defines the implemented v1 subset and resolves the draft's open schema choices.

**The oracle knows the authored grouping, not production reality.** No production statistics, analyzer packages, live services, LLMs, or Prometheus clients are used.

## How to use

Run this snippet from the project root with Python 3.10+, PyYAML 6.0.2, and Matplotlib >=3.10,<4 available. It uses the seeded-variation example and creates `dataset/` plus `timeline.png`; neither output path may already exist.

```sh
# Stop if validation, generation, or rendering fails.
set -e

# 1. Validate the authored example scenario.
python3 -m generator validate --scenario examples/08-seeded-variation/scenario.yaml

# 2. Generate a reproducible dataset from that example.
python3 -m generator generate \
  --scenario examples/08-seeded-variation/scenario.yaml \
  --seed 424242 --output dataset/

# 3. Validate the generated episodes, annotations, and metadata.
python3 -m generator validate --dataset dataset/

# 4. Visualize the dataset as a PNG timeline.
python3 -m tools.visualize --dataset dataset/ --output timeline.png

# 5. Open timeline.png in your image viewer.
```

To try another example, change both `--scenario` arguments. To try another seed, change `--seed` and choose new dataset and PNG output paths, updating the validation and visualization commands accordingly. Only `dataset/episodes.yaml` goes to a grouping algorithm; the PNG includes evaluator reference annotations.

If the dependencies are missing, install the package and plotting extra in your own virtual environment first:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install '.[visualization]'
generator --version
```

Installation may download build tools, PyYAML, and Matplotlib dependencies; generation, validation, and rendering themselves are completely offline. PyYAML is the generator's only runtime dependency and is pinned because serialization is part of reproducibility. The separate PNG visualizer has an optional Matplotlib dependency.

The seed is required, including for fixed scenarios; zero and negative signed 64-bit seeds are valid. Invalid input exits nonzero. Warnings go to stderr and do not make valid inputs fail. Use `--help` on either subcommand for arguments.

## Make shortcuts

The Makefile wraps the same commands; plain `make` prints help without generating files:

```sh
make
make validate-scenario
make generate SEED=424242 OUTPUT=dataset/
make validate-dataset OUTPUT=dataset/
make visualize OUTPUT=dataset/ PNG=timeline.png
make check
```

Defaults are `PYTHON=python3`, `SCENARIO=examples/08-seeded-variation/scenario.yaml`, `SEED=424242`, `OUTPUT=dataset`, and `PNG=timeline.png`. Override them on the command line, for example:

```sh
make generate SCENARIO=examples/01-delayed-symptoms/scenario.yaml SEED=0 OUTPUT=fixed-dataset/
```

`PYTHON` is the Python executable path, not a command with additional flags. `make test` runs the full unittest suite; `make lint` checks Ruff lint and formatting without modifying files; `make typecheck` runs mypy. `make check` runs all three plus compilation, including `tools/`. Ruff and mypy must already be available on `PATH`; full tool verification also requires the visualization extra and `types-PyYAML` stubs in the selected Python environment. Type checking uses `PYTHON` to locate installed dependencies, even when mypy itself comes from a different environment. No target installs dependencies or deletes datasets. Generation and visualization refuse existing output paths.

### Larger example: OpenShift alert storm

[Scenario 09](examples/09-openshift-alert-storm/scenario.yaml) contains **200 episodes, 41 incidents, 19 alert names, and two fictitious clusters**. It combines node outages/flapping, bad rollouts, filesystem exhaustion, network errors, etcd failures, capacity/quota pressure, and eight independent failed-job singletons.

```sh
set -e
make validate-scenario SCENARIO=examples/09-openshift-alert-storm/scenario.yaml
make generate SCENARIO=examples/09-openshift-alert-storm/scenario.yaml SEED=424242 OUTPUT=dataset-09/
make validate-dataset OUTPUT=dataset-09/
make visualize OUTPUT=dataset-09/ PNG=timeline-09.png
```

Use new output paths when rerunning. The PNG reaches the renderer's 200-row limit, so zoom in to inspect it. See the [scenario documentation and pinned OpenShift sources](examples/README.md#09--openshift-alert-storm-200-episodes-with-an-explicit-oracle) for the exact partition, causal assumptions, rule-specific caveats, and authoring provenance. Timing is synthetic, not calibrated from production data; the reference colors are evaluator annotations, not predictions.

## PNG timeline visualization

From the project root, use the separate source-tree tool:

```sh
python3 -m tools.visualize --dataset dataset/ --output timeline.png
# Equivalent:
make visualize OUTPUT=dataset/ PNG=timeline.png
```

It requires Matplotlib 3.10 or newer, below version 4. If it is not already installed, you can install the optional extra in your own environment:

```sh
python -m pip install '.[visualization]'
```

Only this explicit installation may download dependencies. Rendering is offline and headless (Matplotlib's Agg backend); no GUI, browser, external TeX process, or service is used. `tools/` is a source-tree utility, not an additional installed console command. The generator never imports it or Matplotlib.

The image contains:

- One row per episode, sorted by firing start and episode ID.
- A horizontal bar from `start` to `end`, preserving durations and flapping gaps.
- A black diamond at `observed_at`, including observations after resolution. Historical episodes without `observed_at` have no invented marker.
- Reference-incident colors and a legend, with reference IDs also shown in row labels. Flapping episodes sharing a reference ID share a color; unresolved assignments are gray and labeled as unresolved.
- Episode IDs, alert names, namespaces, and other resource labels. Long row labels are abbreviated for readability; the YAML remains the authoritative source of complete values.

**The image includes evaluator annotations, not algorithm predictions.** It is a debugging aid, never an additional input to the grouping algorithm. The tool validates the four canonical dataset files before plotting and does not modify them or add fields to episodes.

Use a new `.png` path whose parent already exists. The image is rendered into a temporary sibling, then published with an exclusive hard link, so existing files (including concurrent outputs) cannot be overwritten and failed renders do not leave partial PNGs. This requires a filesystem supporting hard links; unsupported filesystems fail explicitly rather than falling back to unsafe overwrites.

The deliberately small renderer supports at most **200 episodes per image**, rejecting larger datasets rather than silently omitting episodes. Pagination, interactive filtering, and automatic large-dataset aggregation are not implemented. Similar colors may be difficult to distinguish with many reference incidents; use the textual reference IDs as well. PNG byte identity across Matplotlib/font versions is not promised; the generator's four deterministic dataset artifacts remain unchanged. Matplotlib may use its normal local font cache; set `MPLCONFIGDIR` to a temporary directory if an isolated cache is needed.

## Project layout

```text
AGENTS.md                    contributor boundaries and verification workflow
README.md                    implemented contract and usage
Makefile                     CLI and verification shortcuts; help by default
pyproject.toml               package, YAML dependency, optional plotting extra
docs/GENERATOR.md            original design contract (unchanged)
generator/
  __init__.py                format and generator versions
  __main__.py                argparse CLI
  schema.py                  strict YAML and scenario validation
  generate.py                deterministic causal sampling
  validate.py                episode, annotation, and manifest validation
  output.py                  rendering and safe dataset publication
examples/
  README.md                  catalogue, expected partitions, and exercises
  01-delayed-symptoms/scenario.yaml
  02-overlapping-independent/scenario.yaml
  03-flapping-and-recovery/scenario.yaml
  04-repeated-template/scenario.yaml
  05-singletons-and-background/scenario.yaml
  06-delayed-observation/scenario.yaml
  07-cascading-failure/scenario.yaml
  08-seeded-variation/scenario.yaml
  09-openshift-alert-storm/scenario.yaml
tools/
  __init__.py                optional source-tree tools
  visualize.py               validated dataset → headless timeline PNG
tests/test_generator.py      unittest contract and CLI regression tests
tests/test_visualize.py      plot semantics, PNG output, and publication checks
```

## Input/output separation

The authored `scenario.yaml` stays at its input location. Generation writes exactly:

```text
dataset/
  episodes.yaml              ONLY this file goes to the grouping algorithm
  annotations.yaml           evaluator-only reference partition
  manifest.yaml              versions, seed, input digest, resolved defaults, counts
  dataset-card.md            coverage, warnings, distributions, provenance, limitations
```

Do not pass the scenario, annotations, manifest, or quality card to the algorithm. Join evaluator assignments to algorithm results by `episode_id`. Reference IDs and generation parameters are never injected into episode fields or labels.

The manifest records the SHA-256 of the exact authored input bytes. Archive that scenario separately with the four output files: the hash is not a replacement for the input. Editing even a comment changes the digest and manifest/card bytes, although it does not change sampled times.

## Authored scenario schema

Example using all three distributions:

```yaml
scenario_id: node-failure
version: "0.1"
incidents:
  - incident_template_id: node-failure
    reference_incident_id: incident-1
    target:
      node: node-a
    start:
      distribution: uniform
      min_seconds: 100
      max_seconds: 200
    alerts:
      - role: primary
        alertname: KubeNodeNotReady
        namespace: openshift-monitoring
        labels:
          node: node-a
          severity: warning
        delay:
          distribution: lognormal
          median_seconds: 30
          sigma: 0.4
        duration:
          distribution: fixed
          seconds: 1200
        observation_delay_seconds: 14
```

Fields not listed here are **schema errors**, not ignored extension points:

| Mapping | Required fields | Optional fields |
|---|---|---|
| Scenario | `scenario_id`, `version`, nonempty `incidents` | none |
| Incident | `incident_template_id`, `reference_incident_id`, `start`, nonempty `alerts` | `target` (default `{}`) |
| Alert | `role`, `alertname`, `namespace`, `delay`, `duration` | `labels` (default `{}`), `observation_delay_seconds` (default `0`) |

- IDs and roles use 1–128 ASCII letters, digits, `.`, `_`, or `-`, starting with a letter or digit.
- Each concrete incident has a unique reference ID. `unknown` and `ambiguous` are reserved and cannot be authored oracle incident IDs. Templates may repeat across incidents; roles must be unique **within** each incident.
- Each alert definition emits exactly one episode. For flapping, write multiple definitions with the same labels and different roles/delays, under one incident. Recovery signals are explicit ordinary definitions, not automatically inferred. Use fixed timing when an exact gap is required.
- `alertname` and `namespace` are required nonempty strings and become labels. Other labels are copied exactly, without adding target fields or oracle metadata. A duplicate `alertname`/`namespace` under `labels` must agree with its explicit field.
- Label keys follow `[A-Za-z_][A-Za-z0-9_]*`; internal `__...` keys are rejected. Values must be strings. Quote numeric, boolean-like, and date-like values: PyYAML's YAML 1.1 scalar rules otherwise convert values such as `yes` or `2025-01-01`.
- `target` is optional metadata and a constraint **only on equal keys explicitly present in alert labels**, including `namespace`/`alertname`. `target.node` does not create a `node` label and does not imply an `instance` alias. Do not constrain a changing resource in `target`; write the intended per-episode labels explicitly instead.
- Answer/generator label names such as `reference_incident_id`, `incident_template_id`, `confidence`, `source`, `role`, `delay`, `duration`, and distribution parameters are forbidden, as are `reference_`, `annotation_`, and `generator_` prefixes. Never encode answers under disguised label names either; validation cannot infer arbitrary label-value semantics.
- YAML must be a single UTF-8 document with string mapping keys. Duplicate keys, aliases/merges, unsafe tags, and unsupported fields are rejected. YAML files are limited to 8 MiB.

### Temporal distributions

```text
incident_start = one sampled start shared by the incident
start          = incident_start + sampled alert delay
end            = start + sampled alert duration
observed_at    = start + observation_delay_seconds
```

| Distribution | Required parameters | Semantics |
|---|---|---|
| `fixed` | `seconds` | Exact integer seconds. |
| `uniform` | `min_seconds`, `max_seconds` | Inclusive integer range, with `min_seconds < max_seconds`. Use `fixed` for a constant. |
| `lognormal` | `median_seconds`, `sigma` | Both finite and positive; continuous draw uses `mu = log(median_seconds)`, then rounds. |

Distribution mappings accept only the parameters for their selected type. Missing sigma is an error, including in the draft's abbreviated examples. The median is the pre-rounding 50th percentile, not the arithmetic mean or maximum.

Starts and delays are nonnegative; fixed durations and uniform duration bounds are positive. Observation delay is a nonnegative integer. Lognormal draws round to the nearest second, with half seconds rounded up; a positive duration rounding below one second becomes one second. A small delay may round to zero. These quantization effects mean very small medians do not retain their continuous-distribution interpretation exactly.

Parameters and materialized timestamps are bounded by `2**53 - 1` seconds. Overflow fails with a field error rather than wrapping, clipping large draws, resampling, or leaving a dataset behind. There is no implicit generation window.

### Seed and ordering behavior

SHA-256 derives independent streams from a JSON-encoded tuple containing the root seed, scenario ID, template ID, concrete reference ID, alert role where applicable, and draw purpose. Including the concrete ID prevents repeated templates from sharing a random stream. An unrelated incident or role change does not shift existing draws.

Sampling uses Python's stable seeded `Random.random()` sequence and an explicit Box–Muller transform. It never uses Python's randomized `hash()`. Output has no wall-clock timestamps, absolute paths, or environment-dependent provenance fields; label keys are sorted.

Episodes are serialized in firing-start order; ties retain authored order. IDs are chronological `e-000001`, `e-000002`, etc., rather than exposing reference-partition blocks. Different seeds or edits may change which alert receives an ID: IDs identify episodes **within one materialized dataset**, not across datasets. All seeds retain the same schema and ID structure.

Reproducibility is verified byte-for-byte across all four artifacts and across separate processes with different `PYTHONHASHSEED` values. Tests run with Python 3.12 and pinned PyYAML 6.0.2; cross-platform floating-point behavior at a rounding boundary is not independently certified. Archive materialized output for benchmark comparisons.

## One generated dataset example

```sh
python3 -m generator generate \
  --scenario examples/01-delayed-symptoms/scenario.yaml \
  --seed 424242 --output fixed-dataset/
```

The first records are:

```yaml
# fixed-dataset/episodes.yaml — algorithm input
episodes:
  - episode_id: e-000001
    start: 100
    end: 220
    observed_at: 105
    labels:
      alertname: KubeNodeNotReady
      namespace: openshift-monitoring
      node: node-a
      severity: warning
```

```yaml
# fixed-dataset/annotations.yaml — evaluator only
annotations:
  - episode_id: e-000001
    reference_incident_id: incident-node-a
    confidence: high
    source: synthetic-oracle
```

The other episodes have `(start, end, observed_at)` values `(120, 190, 130)` and `(145, 235, 147)`, also assigned to `incident-node-a`. The manifest identifies `01-delayed-symptoms-seed-424242`, generator `0.1.0`, format/annotation `0.1`, three episodes, and one reference incident. The card lists the distributions, expected low-coverage warnings, and explicitly states that no production-derived statistics were used.

## Validation and publication

`validate --scenario` checks authored schema, distribution parameters, identifiers, labels, and target constraints without sampling. It warns about obvious lack of incident/singleton/parameter variation. Realized overlap, observed order, and sampled duration variation are only meaningful after generation.

`validate --dataset` checks:

- Required fields, versions, types, unique episode IDs, required labels, and absence of answer metadata.
- `start < end`; if present, `observed_at >= start`. Historical input may omit `observed_at`; generated input always includes it. Observation after `end` is valid.
- Exactly one annotation per episode, no duplicate assignments or dangling references, and valid confidence values (`high`, `medium`, `low`). An annotation may include a nonempty `note`.
- Manifest configuration, scenario digest syntax, dataset ID, and counts against materialized records.
- A readable, nonempty quality card. Markdown prose is not a machine-validated schema.

Warnings cover a single resolved incident, no overlapping independent firing intervals, no singletons, simultaneous starts, no duration variation, and more than 10% unresolved annotations. Firing intervals are half-open `[start, end)`: touching endpoints are not overlap. Assignments explicitly marked `unknown` or `ambiguous` are unresolved and excluded from resolved incident counts. Generation itself always emits complete high-confidence synthetic-oracle assignments; the record validator can also inspect individually reviewed assignments with nonempty provenance strings. V1 manifests remain synthetic-oracle manifests, not a general production-dataset format.

A materialized dataset alone cannot prove that labels agree with a missing authored scenario or that a claimed oracle is causally correct. Generation validates those authored constraints first; dataset validation verifies the retained structural invariants, not authenticity or production correctness.

Generation renders and validates everything before publication. Files are staged and flushed in a temporary sibling directory. An exclusive `mkdir` reserves the destination, then directory rename publishes all four files together. A concurrent reader may briefly see an **empty** reservation, never a partially written dataset. Ordinary write/rename failures clean up owned temporary paths. Existing files, directories, and symlinks are refused, even if empty; the output parent must already exist. A process kill or power loss can leave a hidden staging directory or empty reservation requiring manual inspection; power-loss durability is not guaranteed.

## Tests and checks

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q generator tools tests

# If already installed; neither is a runtime dependency:
ruff check --no-cache generator tools tests
ruff format --no-cache --check generator tools tests
mypy --python-executable python3 --no-incremental --cache-dir=/dev/null --check-untyped-defs generator tools tests
```

Tests cover deterministic files, multiple seeds, distributions and invalid parameters, causal/time invariants, metadata isolation, repeated templates, flapping, overlapping independent incidents, duplicate/dangling assignments, strict YAML, output failure cleanup, CLI errors, and every example's intended properties. The type check covers inferred types in function bodies; this small dictionary-based schema implementation is not a fully statically typed data model.

Visualization tests additionally check bar lengths, observation coordinates beyond episode ends, flapping gaps, reference colors, literal (non-TeX) labels, decodable PNGs for all nine examples, input preservation, failure cleanup, and CLI/Make usage. Rendering tests explicitly skip when optional Matplotlib is absent; dependency/error-handling tests still run. Install the visualization extra to exercise all plot checks and type-check its imports.

## Explicit v1 limitations

- No empirical profiles, reusable profile files, `generator-config.yaml`, batch jitter, missing observations, time windows, censoring, or automatic repeat/flap syntax; unsupported fields fail clearly.
- No replay engine, automatic causal/topology inference, production alert-name catalogue, or calibrated timing. Explicit authored resource changes and cascades are supported, not inferred.
- No OpenMetrics exporter or Prometheus dependency. A future exporter must be separate, use canonical episodes, and never export annotation metadata.
- Namespace is required in this v1 format, including for node-oriented examples. No arbitrary namespace is inferred for cluster-scoped alerts.
- Floating-point lognormal sampling and one-second quantization have documented numerical limits; no claim of production realism is made.
