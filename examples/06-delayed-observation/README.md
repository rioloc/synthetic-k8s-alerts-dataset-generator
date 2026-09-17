# 06 — Delayed observation and arrival-order inversion

[Authored scenario](scenario.yaml) · [All examples](../README.md) · [Project setup](../../README.md#how-to-use)

Episode firing order differs from processor arrival order, and one short episode is observed after it has ended. This fixture separates historical/event-time reasoning from streaming release-time behavior.

**Expected output:** 3 episodes, 2 reference incidents; partition sizes **2 + 1**.

## Generate and visualize

Run from the **project root**, not this example directory. Python, PyYAML, Make, and the optional Matplotlib plotting dependency must already be available; see the setup link above.

```sh
set -e

# 1. Validate the authored scenario.
make validate-scenario SCENARIO=examples/06-delayed-observation/scenario.yaml

# 2. Generate with an explicit, reproducible seed.
make generate SCENARIO=examples/06-delayed-observation/scenario.yaml SEED=424242 OUTPUT=dataset-06/

# 3. Validate the materialized dataset.
make validate-dataset OUTPUT=dataset-06/

# 4. Render firing intervals and reference assignments as a PNG.
make visualize OUTPUT=dataset-06/ PNG=timeline-06.png

# 5. Open timeline-06.png in an image viewer.
```

`dataset-06/` and `timeline-06.png` must not already exist. For another run, choose new output paths and use them consistently in steps 2–4. If needed, add `PYTHON=/path/to/python` to each Make command; these commands do not install dependencies.

## Oracle and timing

`incident-node` contains KubeNodeNotReady and TargetDown; `incident-network` contains the unrelated SyntheticNetworkLoss episode on node-b.

The KubeNodeNotReady episode fires at 100, ends at 120, and is observed at 180 because its observation delay is 80 seconds. TargetDown fires and is observed at 115. The independent network signal fires at 130 and is observed at 135.

Historical firing-start order is **KubeNodeNotReady → TargetDown → SyntheticNetworkLoss**. Streaming arrival order is **TargetDown → SyntheticNetworkLoss → KubeNodeNotReady**. `observed_at` must not replace `start`, and seeing an episode after resolution does not change its reference assignment.

In the PNG, the first row's observation diamond lies well to the right of its bar. The other diamonds appear earlier in time even though those episodes occupy later rows. The generator materializes these times; it does not run a replay engine or infer batch jitter.

All timestamps below are relative integer seconds; firing intervals are half-open `[start, end)`. Starts, delays, and durations are fixed, so changing the seed changes dataset metadata but not these intervals.

| Reference incident | Alert (role) | Explicit resource labels | Firing interval | Observed at |
|---|---|---|---|---:|
| `incident-node` | KubeNodeNotReady (`slow-observation`) | `namespace=openshift-monitoring`; `node=node-a` | `[100, 120)` | 180 |
| `incident-node` | TargetDown (`fast-observation`) | `instance=node-a`; `namespace=openshift-monitoring` | `[115, 155)` | 115 |
| `incident-network` | SyntheticNetworkLoss (`network`) | `namespace=openshift-monitoring`; `node=node-b` | `[130, 160)` | 135 |

## Expected warnings and limits

None for the documented seed. Observation after `end` is valid; observation before `start` would be an error.

This is an illustrative fixture, not a simulation of a particular OpenShift release's alert rules. No production-derived timing statistics are used. Correct synthetic reference assignments do not establish production-realistic timing or incident prevalence.

Only `dataset-06/episodes.yaml` goes to a grouping algorithm. `annotations.yaml`, the manifest, quality card, and PNG are evaluator/debugging artifacts. The PNG colors show reference assignments, not algorithm predictions, and may abbreviate long labels; retain the YAML as the authoritative record.
