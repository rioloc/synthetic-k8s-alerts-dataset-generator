# 04 — Repeated templates and separate occurrences

[Authored scenario](scenario.yaml) · [All examples](../README.md) · [Project setup](../../README.md#how-to-use)

The same incident template is used three times, including two separate failures on node-a. This fixture checks that a reusable template or repeated resource identity is not mistaken for one concrete incident.

**Expected output:** 5 episodes, 3 reference incidents; partition sizes **2 + 2 + 1**.

## Generate and visualize

Run from the **project root**, not this example directory. Python, PyYAML, Make, and the optional Matplotlib plotting dependency must already be available; see the setup link above.

```sh
set -e

# 1. Validate the authored scenario.
make validate-scenario SCENARIO=examples/04-repeated-template/scenario.yaml

# 2. Generate with an explicit, reproducible seed.
make generate SCENARIO=examples/04-repeated-template/scenario.yaml SEED=424242 OUTPUT=dataset-04/

# 3. Validate the materialized dataset.
make validate-dataset OUTPUT=dataset-04/

# 4. Render firing intervals and reference assignments as a PNG.
make visualize OUTPUT=dataset-04/ PNG=timeline-04.png

# 5. Open timeline-04.png in an image viewer.
```

`dataset-04/` and `timeline-04.png` must not already exist. For another run, choose new output paths and use them consistently in steps 2–4. If needed, add `PYTHON=/path/to/python` to each Make command; these commands do not install dependencies.

## Oracle and timing

All three incidents use `incident_template_id: node-failure`. Roles such as `primary` and `target-down` are reused across incidents, which is valid: role uniqueness is local to each occurrence.

- `incident-a-first`: the first node-a failure, with two episodes beginning at 100 and 110 seconds.
- `incident-a-second`: a new node-a failure, with two episodes beginning at 300 and 315 seconds.
- `incident-b`: a one-episode node-b failure beginning at 320 seconds, overlapping the second node-a occurrence.

Unlike example 03, the two node-a failures are authored as separate reference incidents, not flapping within one incident. That is an oracle modeling choice; timing and identical labels alone do not prove the causal distinction.

In the PNG, expect three reference colors with group sizes 2, 2, and 1. The two node-a occurrences have different colors despite sharing alert/resource labels. All observation delays are zero.

All timestamps below are relative integer seconds; firing intervals are half-open `[start, end)`. Starts, delays, and durations are fixed, so changing the seed changes dataset metadata but not these intervals.

| Reference incident | Alert (role) | Explicit resource labels | Firing interval | Observed at |
|---|---|---|---|---:|
| `incident-a-first` | KubeNodeNotReady (`primary`) | `namespace=openshift-monitoring`; `node=node-a` | `[100, 150)` | 100 |
| `incident-a-first` | TargetDown (`target-down`) | `instance=node-a`; `namespace=openshift-monitoring` | `[110, 140)` | 110 |
| `incident-a-second` | KubeNodeNotReady (`primary`) | `namespace=openshift-monitoring`; `node=node-a` | `[300, 360)` | 300 |
| `incident-a-second` | TargetDown (`target-down`) | `instance=node-a`; `namespace=openshift-monitoring` | `[315, 340)` | 315 |
| `incident-b` | KubeNodeNotReady (`primary`) | `namespace=openshift-monitoring`; `node=node-b` | `[320, 350)` | 320 |

## Expected warnings and limits

None for the documented seed. Independent overlap, a singleton, and different delays/durations are present.

This is an illustrative fixture, not a simulation of a particular OpenShift release's alert rules. No production-derived timing statistics are used. Correct synthetic reference assignments do not establish production-realistic timing or incident prevalence.

Only `dataset-04/episodes.yaml` goes to a grouping algorithm. `annotations.yaml`, the manifest, quality card, and PNG are evaluator/debugging artifacts. The PNG colors show reference assignments, not algorithm predictions, and may abbreviate long labels; retain the YAML as the authoritative record.
