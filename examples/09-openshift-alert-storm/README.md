# 09 — OpenShift alert storm: 200 episodes

[Authored scenario](scenario.yaml) · [All examples](../README.md) · [Project setup](../../README.md#how-to-use)

A larger grouping-quality fixture combines eight fault families across two fictitious clusters. It uses a versioned OpenShift alert-rule baseline documented in the central catalogue, but its causal assignments and timing remain authored synthetic assumptions—not a production incident trace.

**Expected output:** 200 episodes, 41 reference incidents; partition sizes **8×1 + 14×5 + 15×6 + 4×8**.

## Generate and visualize

Run from the **project root**, not this example directory. Python, PyYAML, Make, and the optional Matplotlib plotting dependency must already be available; see the setup link above.

```sh
set -e

# 1. Validate the authored scenario.
make validate-scenario SCENARIO=examples/09-openshift-alert-storm/scenario.yaml

# 2. Generate with an explicit, reproducible seed.
make generate SCENARIO=examples/09-openshift-alert-storm/scenario.yaml SEED=424242 OUTPUT=dataset-09/

# 3. Validate the materialized dataset.
make validate-dataset OUTPUT=dataset-09/

# 4. Render firing intervals and reference assignments as a PNG.
make visualize OUTPUT=dataset-09/ PNG=timeline-09.png

# 5. Open timeline-09.png in an image viewer. Zoom in: there are 200 rows.
```

`dataset-09/` and `timeline-09.png` must not already exist. For another run, choose new output paths and use them consistently in steps 2–4. If needed, add `PYTHON=/path/to/python` to each Make command; these commands do not install dependencies.

## Oracle and timing

The clusters `synthetic-east` and `synthetic-west`, their workloads, and their resources are fictitious; hostnames use `.example.invalid`. Both clusters reuse ordinary namespace/resource names. A `cluster` label is a resource boundary, not an oracle ID: each cluster contains many independent incidents.

| Fault template | Concrete incidents | Episodes per incident | Total episodes |
|---|---:|---:|---:|
| `node-outage-flapping` | 10 | 5 | 50 |
| `bad-rollout` | 6 | 6 | 36 |
| `filesystem-exhaustion` | 5 | 6 | 30 |
| `network-degradation` | 4 | 6 | 24 |
| `etcd-disk-latency` | 2 | 8 | 16 |
| `etcd-quorum-loss` | 2 | 8 | 16 |
| `capacity-and-quota-pressure` | 4 | 5 | 20 |
| `isolated-job-failure` | 8 | 1 | 8 |
| **Total** | **41** | | **200** |

There are **8 singleton incidents**, **19 alert names**, and no unresolved assignments. Labels include 166 warning, 22 critical, and 12 info episodes. Each episode receives one high-confidence `synthetic-oracle` assignment; confidence means certainty about the authored grouping, not confidence in a production diagnosis.

Incident starts use uniform distributions in multiple waves. Delays are fixed or bounded uniform values; durations mix fixed, uniform, and lognormal profiles with positive sigma. Each alert inherits its incident origin. Observation delays are explicit constants, not independent firing-time randomization.

For seed `424242`, firing starts begin at **1191 seconds** and the latest firing end is **25323 seconds**. These are observed bounds, not a generation window. There are **3 episodes observed after their firing end**, and arrival order differs from firing-start order. Other seeds change sampled times, not the authored partition sizes.

### What to inspect in the PNG

- **Independent overlap:** unrelated incidents can share cluster, namespace, alert name, and nearby timestamps without sharing a reference assignment.
- **Cross-component grouping:** one authored cause can span node, pod, deployment, interface, filesystem, or etcd symptoms with different labels and durations.
- **Flapping versus new incidents:** node/network incidents contain two explicit KubeNodeNotReady episodes with identical labels and at least a 900-second firing gap, retaining one reference ID. Later etcd quorum losses are separate from earlier disk-latency incidents.
- **Severity is not identity:** filesystem critical intervals are nested inside warning intervals for the same resource and reference incident. These are raw firing episodes, not an inhibited Alertmanager notification stream.
- **Singletons and delayed observation:** isolated job failures keep their own references; observation diamonds can occur after short bars have ended.

## Source-rule and provenance cautions

The existing catalogue records a pinned OpenShift `release-4.18` operator-rule baseline and immutable public source links. See [source-rule constraints](../README.md#temporal-model-and-source-rule-constraints) and [sources and authoring provenance](../README.md#sources-and-how-they-were-used) for the detailed evidence and qualifications.

- Alert delays were authored to respect the documented pending `for` periods, but the generator does not evaluate PromQL, metric history, thresholds, request-volume gates, or alert transitions. Rule names and delays alone do not prove that the alerts would actually fire together.
- The documented KubePodNotReady expression selects Pending/Unknown pods and excludes unschedulable pods; it is not a generic running-pod readiness-failure signal. Rollout incidents instead pair crash loops with KubeDeploymentRolloutStuck.
- CPU/memory overcommit concerns resource requests and failure tolerance, not measured utilization. Quota-almost-full signals are info severity. Explicit namespaces and aggregation scopes must not be replaced by invented node or instance attribution.
- Quorum-loss observations are attributed to a surviving member where appropriate. Complete monitoring visibility during a real control-plane outage is still a simplification.

**AI-assisted authoring:** this scenario was assembled with AI assistance, as recorded in its existing header and catalogue. The current generator manifest/card hard-code `llm_assisted: false` / no LLM assistance and do not represent scenario-authoring provenance. Do not cite those generated fields as evidence that this scenario was authored without AI assistance. This README preserves that caveat without changing the metadata contract.

Fault combinations, frequency, wave spacing, resource relationships, timing distributions, and recovery order remain authored choices. Public rule/runbook references are not production-derived timing statistics or unique causal proofs. No live cluster or upstream service is needed to use the fixture.

## Expected warnings and limits

None for seed `424242`. The 200-row PNG reaches the current renderer limit; zoom in to inspect individual rows. It is not a million-alert throughput benchmark.

No production-derived timing statistics are used. Correct synthetic reference assignments do not establish production-realistic timing or incident prevalence.

Only `dataset-09/episodes.yaml` goes to a grouping algorithm. `annotations.yaml`, the manifest, quality card, and PNG are evaluator/debugging artifacts. The PNG colors show reference assignments, not algorithm predictions, and may abbreviate long labels; retain the YAML as the authoritative record.
