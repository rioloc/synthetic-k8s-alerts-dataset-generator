# 03 — Flapping, recovery, and an unrelated overlap

[Authored scenario](scenario.yaml) · [All examples](../README.md) · [Project setup](../../README.md#how-to-use)

One node fires twice with a gap and then emits an explicitly modeled recovery signal. A separate pod incident overlaps the second firing. This distinguishes within-incident flapping from unrelated concurrent activity.

**Expected output:** 4 episodes, 2 reference incidents; partition sizes **3 + 1**.

## Generate and visualize

Run from the **project root**, not this example directory. Python, PyYAML, Make, and the optional Matplotlib plotting dependency must already be available; see the setup link above.

```sh
set -e

# 1. Validate the authored scenario.
make validate-scenario SCENARIO=examples/03-flapping-and-recovery/scenario.yaml

# 2. Generate with an explicit, reproducible seed.
make generate SCENARIO=examples/03-flapping-and-recovery/scenario.yaml SEED=424242 OUTPUT=dataset-03/

# 3. Validate the materialized dataset.
make validate-dataset OUTPUT=dataset-03/

# 4. Render firing intervals and reference assignments as a PNG.
make visualize OUTPUT=dataset-03/ PNG=timeline-03.png

# 5. Open timeline-03.png in an image viewer.
```

`dataset-03/` and `timeline-03.png` must not already exist. For another run, choose new output paths and use them consistently in steps 2–4. If needed, add `PYTHON=/path/to/python` to each Make command; these commands do not install dependencies.

## Oracle and timing

`incident-flapping` contains the two KubeNodeNotReady episodes and SyntheticNodeRecovered. The two firing episodes have identical labels but distinct roles and episode IDs. Their intervals are `[100, 130)` and `[170, 195)`, leaving a 40-second firing gap.

The recovery signal is an ordinary, explicitly authored episode at `[200, 210)`, with severity `info`. It is not automatically generated from an episode's end and is not a claim that this rule exists in OpenShift.

`incident-unrelated` is KubePodCrashLooping on node-b at `[175, 215)`, a singleton that overlaps the second firing and recovery. In the PNG, three rows share one reference color, while the unrelated pod has another. All observation delays are zero.

All timestamps below are relative integer seconds; firing intervals are half-open `[start, end)`. Starts, delays, and durations are fixed, so changing the seed changes dataset metadata but not these intervals.

| Reference incident | Alert (role) | Explicit resource labels | Firing interval | Observed at |
|---|---|---|---|---:|
| `incident-flapping` | KubeNodeNotReady (`firing-first`) | `namespace=openshift-monitoring`; `node=node-a` | `[100, 130)` | 100 |
| `incident-flapping` | KubeNodeNotReady (`firing-second`) | `namespace=openshift-monitoring`; `node=node-a` | `[170, 195)` | 170 |
| `incident-flapping` | SyntheticNodeRecovered (`recovery`) | `namespace=openshift-monitoring`; `node=node-a` | `[200, 210)` | 200 |
| `incident-unrelated` | KubePodCrashLooping (`restart`) | `namespace=openshift-monitoring`; `node=node-b`; `pod=worker-b` | `[175, 215)` | 175 |

## Expected warnings and limits

None for the documented seed. A singleton, independent overlap, and delay/duration variation are present.

This is an illustrative fixture, not a simulation of a particular OpenShift release's alert rules. No production-derived timing statistics are used. Correct synthetic reference assignments do not establish production-realistic timing or incident prevalence.

Only `dataset-03/episodes.yaml` goes to a grouping algorithm. `annotations.yaml`, the manifest, quality card, and PNG are evaluator/debugging artifacts. The PNG colors show reference assignments, not algorithm predictions, and may abbreviate long labels; retain the YAML as the authoritative record.
