# 07 — A cross-component cascade with resource changes

[Authored scenario](scenario.yaml) · [All examples](../README.md) · [Project setup](../../README.md#how-to-use)

One authored cascade spans network, database, API, and replacement-pod symptoms. An unrelated API failure overlaps it in the same namespace. This challenges both splitting by resource labels and merging by namespace/alert name.

**Expected output:** 5 episodes, 2 reference incidents; partition sizes **4 + 1**.

## Generate and visualize

Run from the **project root**, not this example directory. Python, PyYAML, Make, and the optional Matplotlib plotting dependency must already be available; see the setup link above.

```sh
set -e

# 1. Validate the authored scenario.
make validate-scenario SCENARIO=examples/07-cascading-failure/scenario.yaml

# 2. Generate with an explicit, reproducible seed.
make generate SCENARIO=examples/07-cascading-failure/scenario.yaml SEED=424242 OUTPUT=dataset-07/

# 3. Validate the materialized dataset.
make validate-dataset OUTPUT=dataset-07/

# 4. Render firing intervals and reference assignments as a PNG.
make visualize OUTPUT=dataset-07/ PNG=timeline-07.png

# 5. Open timeline-07.png in an image viewer.
```

`dataset-07/` and `timeline-07.png` must not already exist. For another run, choose new output paths and use them consistently in steps 2–4. If needed, add `PYTHON=/path/to/python` to each Make command; these commands do not install dependencies.

## Oracle and timing

`incident-cascade` contains four episodes: network loss on node-edge, database unavailability on db-1, API errors on node-api, and database unavailability on replacement pod db-2. The shared target constrains only `namespace: payments`, permitting explicitly different node, pod, and service labels.

The database labels change from `pod: db-1` to `pod: db-2`. Their intervals overlap during the modeled handover, but both retain the cascade's reference assignment. No Kubernetes controller lifecycle or topology is simulated.

`incident-other-api` is SyntheticHighErrorRate for `service: reports`, beginning at 140 seconds, exactly when the cascade's `service: api` symptom starts. Namespace, alert name, and timestamp all match, but the authored causes are different.

In the PNG, expect four rows of one reference color across different resources and one differently colored reports-service row. All observation delays are zero. These `Synthetic...` signals and causal links are explicit modeling choices, not production rule claims or automatic inference.

All timestamps below are relative integer seconds; firing intervals are half-open `[start, end)`. Starts, delays, and durations are fixed, so changing the seed changes dataset metadata but not these intervals.

| Reference incident | Alert (role) | Explicit resource labels | Firing interval | Observed at |
|---|---|---|---|---:|
| `incident-cascade` | SyntheticNetworkLoss (`network-root`) | `namespace=payments`; `node=node-edge` | `[100, 260)` | 100 |
| `incident-cascade` | SyntheticDatabaseUnavailable (`database`) | `namespace=payments`; `node=node-db`; `pod=db-1` | `[120, 220)` | 120 |
| `incident-cascade` | SyntheticHighErrorRate (`api`) | `namespace=payments`; `node=node-api`; `service=api` | `[140, 220)` | 140 |
| `incident-cascade` | SyntheticDatabaseUnavailable (`replacement-pod`) | `namespace=payments`; `node=node-db`; `pod=db-2` | `[165, 210)` | 165 |
| `incident-other-api` | SyntheticHighErrorRate (`api`) | `namespace=payments`; `node=node-reports`; `service=reports` | `[140, 190)` | 140 |

## Expected warnings and limits

None for the documented seed. The separate reports-service incident supplies a singleton and independent overlap.

This is an illustrative fixture, not a simulation of a particular OpenShift release's alert rules. No production-derived timing statistics are used. Correct synthetic reference assignments do not establish production-realistic timing or incident prevalence.

Only `dataset-07/episodes.yaml` goes to a grouping algorithm. `annotations.yaml`, the manifest, quality card, and PNG are evaluator/debugging artifacts. The PNG colors show reference assignments, not algorithm predictions, and may abbreviate long labels; retain the YAML as the authoritative record.
