# 02 — Overlapping but independent node failures

[Authored scenario](scenario.yaml) · [All examples](../README.md) · [Project setup](../../README.md#how-to-use)

Two unrelated node failures share a namespace, template, alert names, and overlapping time windows. This fixture challenges over-grouping based only on temporal proximity or a common namespace.

**Expected output:** 4 episodes, 2 reference incidents; partition sizes **2 + 2**.

## Generate and visualize

Run from the **project root**, not this example directory. Python, PyYAML, Make, and the optional Matplotlib plotting dependency must already be available; see the setup link above.

```sh
set -e

# 1. Validate the authored scenario.
make validate-scenario SCENARIO=examples/02-overlapping-independent/scenario.yaml

# 2. Generate with an explicit, reproducible seed.
make generate SCENARIO=examples/02-overlapping-independent/scenario.yaml SEED=424242 OUTPUT=dataset-02/

# 3. Validate the materialized dataset.
make validate-dataset OUTPUT=dataset-02/

# 4. Render firing intervals and reference assignments as a PNG.
make visualize OUTPUT=dataset-02/ PNG=timeline-02.png

# 5. Open timeline-02.png in an image viewer.
```

`dataset-02/` and `timeline-02.png` must not already exist. For another run, choose new output paths and use them consistently in steps 2–4. If needed, add `PYTHON=/path/to/python` to each Make command; these commands do not install dependencies.

## Oracle and timing

`incident-node-a` contains both symptoms on node-a; `incident-node-b` contains both symptoms on node-b. Each occurrence uses the reusable `node-failure` template, but the reference incidents remain separate.

Both incidents use `openshift-monitoring`. Resource labels distinguish their targets: `node` for KubeNodeNotReady and `instance` for TargetDown. Their relationship is explicit in the scenario, not inferred through a label-alias mapping.

In the PNG, expect two reference colors interleaved in firing-start order. Each color occurs twice, and bars from the two incidents overlap. All observation delays are zero, so diamonds sit at the bar starts.

All timestamps below are relative integer seconds; firing intervals are half-open `[start, end)`. Starts, delays, and durations are fixed, so changing the seed changes dataset metadata but not these intervals.

| Reference incident | Alert (role) | Explicit resource labels | Firing interval | Observed at |
|---|---|---|---|---:|
| `incident-node-a` | KubeNodeNotReady (`primary`) | `namespace=openshift-monitoring`; `node=node-a` | `[100, 280)` | 100 |
| `incident-node-a` | TargetDown (`target-down`) | `instance=node-a`; `namespace=openshift-monitoring` | `[120, 240)` | 120 |
| `incident-node-b` | KubeNodeNotReady (`primary`) | `namespace=openshift-monitoring`; `node=node-b` | `[110, 260)` | 110 |
| `incident-node-b` | TargetDown (`target-down`) | `instance=node-b`; `namespace=openshift-monitoring` | `[135, 225)` | 135 |

## Expected warnings and limits

No singleton incidents. Independent overlap and duration variation are present; the absence of singletons is intentional.

This is an illustrative fixture, not a simulation of a particular OpenShift release's alert rules. No production-derived timing statistics are used. Correct synthetic reference assignments do not establish production-realistic timing or incident prevalence.

Only `dataset-02/episodes.yaml` goes to a grouping algorithm. `annotations.yaml`, the manifest, quality card, and PNG are evaluator/debugging artifacts. The PNG colors show reference assignments, not algorithm predictions, and may abbreviate long labels; retain the YAML as the authoritative record.
