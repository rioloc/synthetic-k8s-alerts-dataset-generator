# 01 — Delayed symptoms: a hand-checkable baseline

[Authored scenario](scenario.yaml) · [All examples](../README.md) · [Project setup](../../README.md#how-to-use)

One node failure produces three symptoms with different delays, durations, and observation times. Use this smallest fixture to check interval handling and to expose unnecessary splitting of symptoms that the authored oracle assigns together.

**Expected output:** 3 episodes, 1 reference incident; partition sizes **3**.

## Generate and visualize

Run from the **project root**, not this example directory. Python, PyYAML, Make, and the optional Matplotlib plotting dependency must already be available; see the setup link above.

```sh
set -e

# 1. Validate the authored scenario.
make validate-scenario SCENARIO=examples/01-delayed-symptoms/scenario.yaml

# 2. Generate with an explicit, reproducible seed.
make generate SCENARIO=examples/01-delayed-symptoms/scenario.yaml SEED=424242 OUTPUT=dataset-01/

# 3. Validate the materialized dataset.
make validate-dataset OUTPUT=dataset-01/

# 4. Render firing intervals and reference assignments as a PNG.
make visualize OUTPUT=dataset-01/ PNG=timeline-01.png

# 5. Open timeline-01.png in an image viewer.
```

`dataset-01/` and `timeline-01.png` must not already exist. For another run, choose new output paths and use them consistently in steps 2–4. If needed, add `PYTHON=/path/to/python` to each Make command; these commands do not install dependencies.

## Oracle and timing

All three episodes belong to `incident-node-a`, whose shared incident start is 100 seconds. Their delays are 0, 20, and 45 seconds; durations are 120, 70, and 90 seconds. Observation delays are 5, 10, and 2 seconds respectively.

The `TargetDown` episode explicitly carries `instance: node-a`, not a `node` label. `target.node` is scenario metadata: it is neither injected into labels nor treated as an automatic `instance` alias.

In the PNG, expect three bars of one reference color with staggered left edges and observation diamonds after each firing start. Different end times do not create new reference incidents.

All timestamps below are relative integer seconds; firing intervals are half-open `[start, end)`. Starts, delays, and durations are fixed, so changing the seed changes dataset metadata but not these intervals.

| Reference incident | Alert (role) | Explicit resource labels | Firing interval | Observed at |
|---|---|---|---|---:|
| `incident-node-a` | KubeNodeNotReady (`primary`) | `namespace=openshift-monitoring`; `node=node-a` | `[100, 220)` | 105 |
| `incident-node-a` | TargetDown (`target-down`) | `instance=node-a`; `namespace=openshift-monitoring` | `[120, 190)` | 130 |
| `incident-node-a` | KubeNodeUnreachable (`unreachable`) | `namespace=openshift-monitoring`; `node=node-a` | `[145, 235)` | 147 |

## Expected warnings and limits

Only one incident, no overlapping independent incidents, and no singleton incidents. These are intentional coverage limitations, not validation failures.

This is an illustrative fixture, not a simulation of a particular OpenShift release's alert rules. No production-derived timing statistics are used. Correct synthetic reference assignments do not establish production-realistic timing or incident prevalence.

Only `dataset-01/episodes.yaml` goes to a grouping algorithm. `annotations.yaml`, the manifest, quality card, and PNG are evaluator/debugging artifacts. The PNG colors show reference assignments, not algorithm predictions, and may abbreviate long labels; retain the YAML as the authoritative record.
