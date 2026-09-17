# 05 — Singletons and long-lived background activity

[Authored scenario](scenario.yaml) · [All examples](../README.md) · [Project setup](../../README.md#how-to-use)

A long-lived Watchdog overlaps a multi-alert deployment failure and an isolated OOM signal. This fixture challenges the tendency to absorb every concurrent episode into one large group or to lose singletons.

**Expected output:** 5 episodes, 3 reference incidents; partition sizes **1 + 3 + 1**.

## Generate and visualize

Run from the **project root**, not this example directory. Python, PyYAML, Make, and the optional Matplotlib plotting dependency must already be available; see the setup link above.

```sh
set -e

# 1. Validate the authored scenario.
make validate-scenario SCENARIO=examples/05-singletons-and-background/scenario.yaml

# 2. Generate with an explicit, reproducible seed.
make generate SCENARIO=examples/05-singletons-and-background/scenario.yaml SEED=424242 OUTPUT=dataset-05/

# 3. Validate the materialized dataset.
make validate-dataset OUTPUT=dataset-05/

# 4. Render firing intervals and reference assignments as a PNG.
make visualize OUTPUT=dataset-05/ PNG=timeline-05.png

# 5. Open timeline-05.png in an image viewer.
```

`dataset-05/` and `timeline-05.png` must not already exist. For another run, choose new output paths and use them consistently in steps 2–4. If needed, add `PYTHON=/path/to/python` to each Make command; these commands do not install dependencies.

## Oracle and timing

- `incident-watchdog`: Watchdog at `[0, 600)` in `openshift-monitoring`, with severity `none`.
- `incident-deployment`: three symptoms in `payments`, relating the `api` deployment, its pod, and service availability.
- `incident-oom`: a SyntheticContainerOOM episode for `batch-1` in `batch` at `[220, 240)`.

Watchdog is deliberately its own singleton reference incident **in this fixture**. This is not a universal statement that background alerts represent incidents or should always be included in evaluation. Excluding background activity requires a different authored benchmark convention, not silently changing these assignments.

In the PNG, expect one long Watchdog bar, three deployment-colored rows, and a short OOM bar with its own reference color. The Watchdog interval spans every other episode. All observation delays are zero. The two `Synthetic...` names are illustrative signals, not claims of installed production rules.

All timestamps below are relative integer seconds; firing intervals are half-open `[start, end)`. Starts, delays, and durations are fixed, so changing the seed changes dataset metadata but not these intervals.

| Reference incident | Alert (role) | Explicit resource labels | Firing interval | Observed at |
|---|---|---|---|---:|
| `incident-watchdog` | Watchdog (`watchdog`) | `namespace=openshift-monitoring` | `[0, 600)` | 0 |
| `incident-deployment` | KubeDeploymentReplicasMismatch (`replicas`) | `deployment=api`; `namespace=payments` | `[100, 250)` | 100 |
| `incident-deployment` | KubePodCrashLooping (`pod`) | `deployment=api`; `namespace=payments`; `pod=api-1` | `[115, 205)` | 115 |
| `incident-deployment` | SyntheticServiceUnavailable (`availability`) | `namespace=payments`; `service=api` | `[130, 230)` | 130 |
| `incident-oom` | SyntheticContainerOOM (`oom`) | `namespace=batch`; `pod=batch-1` | `[220, 240)` | 220 |

## Expected warnings and limits

None for the documented seed. Two singletons and independent overlap are deliberately included.

This is an illustrative fixture, not a simulation of a particular OpenShift release's alert rules. No production-derived timing statistics are used. Correct synthetic reference assignments do not establish production-realistic timing or incident prevalence.

Only `dataset-05/episodes.yaml` goes to a grouping algorithm. `annotations.yaml`, the manifest, quality card, and PNG are evaluator/debugging artifacts. The PNG colors show reference assignments, not algorithm predictions, and may abbreviate long labels; retain the YAML as the authoritative record.
