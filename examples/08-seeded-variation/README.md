# 08 — Reproducible temporal variation

[Authored scenario](scenario.yaml) · [All examples](../README.md) · [Project setup](../../README.md#how-to-use)

Two independent node incidents use sampled incident starts, role-specific delays, and different durations; a fixed pod restart supplies a singleton. This is the stochastic counterpart to the smaller fixed-timing fixtures.

**Expected output:** 5 episodes, 3 reference incidents; partition sizes **2 + 2 + 1**.

## Generate and visualize

Run from the **project root**, not this example directory. Python, PyYAML, Make, and the optional Matplotlib plotting dependency must already be available; see the setup link above.

```sh
set -e

# 1. Validate the authored scenario.
make validate-scenario SCENARIO=examples/08-seeded-variation/scenario.yaml

# 2. Generate with an explicit, reproducible seed.
make generate SCENARIO=examples/08-seeded-variation/scenario.yaml SEED=424242 OUTPUT=dataset-08/

# 3. Validate the materialized dataset.
make validate-dataset OUTPUT=dataset-08/

# 4. Render firing intervals and reference assignments as a PNG.
make visualize OUTPUT=dataset-08/ PNG=timeline-08.png

# 5. Open timeline-08.png in an image viewer.
```

`dataset-08/` and `timeline-08.png` must not already exist. For another run, choose new output paths and use them consistently in steps 2–4. If needed, add `PYTHON=/path/to/python` to each Make command; these commands do not install dependencies.

## Oracle and timing

Both node incidents use the `node-failure` template but have different reference IDs and targets. `incident-node-a` has a uniform incident start in `[100, 200]`; `incident-node-b` uses `[150, 250]`. Their alerts inherit the sampled incident origin rather than receiving unrelated random start timestamps.

`incident-restart` starts at 180 seconds and produces one fixed episode at `[180, 205)`, observed at 183. The node incidents contain KubeNodeNotReady and TargetDown each, with the profiles below.

`U(a, b)` denotes an inclusive integer uniform distribution. `LN(m, s)` denotes a lognormal distribution with median `m` seconds and positive sigma `s`; the median is not the arithmetic mean. Lognormal draws round to integer seconds, and positive durations have a one-second minimum.

| Reference incident | Alert | Delay | Duration | Observation delay |
|---|---|---|---|---:|
| `incident-node-a` | KubeNodeNotReady | LN(30, 0.4) | LN(1200, 0.5) | 14 s |
| `incident-node-a` | TargetDown | LN(60, 0.4) | LN(900, 0.5) | 5 s |
| `incident-node-b` | KubeNodeNotReady | U(10, 40) | LN(800, 0.3) | 20 s |
| `incident-node-b` | TargetDown | LN(45, 0.5) | U(400, 700) | 0 s |
| `incident-restart` | KubePodCrashLooping | Fixed 0 s | Fixed 25 s | 3 s |

At seed `424242`, the earliest firing start is 180 seconds and the latest end is 1233 seconds; these are sampled output bounds, not a configured window. The PNG shows two independently colored node groups plus the short restart singleton.

Repeat the same scenario and seed into a new directory to obtain byte-identical canonical files. Change the seed to vary sampled times while preserving the authored reference memberships and partition sizes. Chronological episode IDs identify a single materialization and must not be used to join different-seed datasets. No observation jitter or missing observations are inferred.

## Expected warnings and limits

None for seed `424242`. That seed includes independent overlap; overlap is not guaranteed for every seed because lognormal tails are unbounded.

This is an illustrative fixture, not a simulation of a particular OpenShift release's alert rules. No production-derived timing statistics are used. Correct synthetic reference assignments do not establish production-realistic timing or incident prevalence.

Only `dataset-08/episodes.yaml` goes to a grouping algorithm. `annotations.yaml`, the manifest, quality card, and PNG are evaluator/debugging artifacts. The PNG colors show reference assignments, not algorithm predictions, and may abbreviate long labels; retain the YAML as the authoritative record.
