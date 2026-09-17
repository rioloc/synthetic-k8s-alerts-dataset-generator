# Input example catalogue

These are authored synthetic oracle scenarios, not collected alerts and not assertions about how any particular grouping algorithm should behave. Expected partitions describe the evaluator's truth for these fixtures. Names beginning with `Synthetic` are illustrative signals, not claims that those alert rules exist in OpenShift.

Examples 01–07 use fixed integer timing so their relationships can be checked by hand. Example 08 adds all three supported distributions; example 09 scales up to 200 episodes using a versioned OpenShift alert-rule baseline. The seed is required for every example; `424242` is the documented baseline.

## Generate and inspect

From the project root:

```sh
python3 -m generator validate --scenario examples/02-overlapping-independent/scenario.yaml
python3 -m generator generate \
  --scenario examples/02-overlapping-independent/scenario.yaml \
  --seed 424242 --output overlap-dataset/
python3 -m generator validate --dataset overlap-dataset/
```

To generate the complete catalogue without overwriting previous output:

```sh
output=$(mktemp -d)
for scenario in examples/*/scenario.yaml; do
  name=$(basename "$(dirname "$scenario")")
  python3 -m generator generate \
    --scenario "$scenario" --seed 424242 --output "$output/$name" || exit 1
done
printf 'Datasets retained in %s\n' "$output"
```

Give only each dataset's `episodes.yaml` to an algorithm. The evaluator loads `annotations.yaml` separately. Do not compare episode IDs across datasets; they are assigned in firing-start order and identify only one materialization.

## Catalogue and expected oracle partitions

| Scenario | Episodes / incidents | Expected partition sizes | Main challenge |
|---|---:|---|---|
| [01-delayed-symptoms](01-delayed-symptoms/scenario.yaml) | 3 / 1 | 3 | Symptoms do not have identical starts or durations. |
| [02-overlapping-independent](02-overlapping-independent/scenario.yaml) | 4 / 2 | 2 + 2 | Namespace, alert name, and timing similarity can over-merge independent targets. |
| [03-flapping-and-recovery](03-flapping-and-recovery/scenario.yaml) | 4 / 2 | 3 + 1 | A gap and a recovery signal do not necessarily define a new reference incident. |
| [04-repeated-template](04-repeated-template/scenario.yaml) | 5 / 3 | 2 + 2 + 1 | Template reuse and repeated failure on one resource do not imply shared occurrence identity. |
| [05-singletons-and-background](05-singletons-and-background/scenario.yaml) | 5 / 3 | 1 + 3 + 1 | Long-lived background activity must not automatically absorb unrelated symptoms. |
| [06-delayed-observation](06-delayed-observation/scenario.yaml) | 3 / 2 | 2 + 1 | Event-time and arrival-time order disagree. |
| [07-cascading-failure](07-cascading-failure/scenario.yaml) | 5 / 2 | 4 + 1 | A cross-component cascade coexists with a similar but unrelated symptom. |
| [08-seeded-variation](08-seeded-variation/scenario.yaml) | 5 / 3 | 2 + 2 + 1 | Reproducible variation without destroying the shared incident origin. |
| [09-openshift-alert-storm](09-openshift-alert-storm/scenario.yaml) | 200 / 41 | 8×1 + 14×5 + 15×6 + 4×8 | Concurrent fault families, cross-component symptoms, recurrence, and a large reference timeline. |

### 01 — Delayed symptoms: a hand-checkable baseline

All three episodes belong to `incident-node-a`:

| Alert | Firing interval | Observed at |
|---|---|---:|
| KubeNodeNotReady | `[100, 220)` | 105 |
| TargetDown | `[120, 190)` | 130 |
| KubeNodeUnreachable | `[145, 235)` | 147 |

The incident starts at 100; delays are 0, 20, and 45 seconds. The `TargetDown` definition explicitly has `instance: node-a`, not an injected `node` label. Warnings about one incident, no independent overlap, and no singletons are intentional. This is a correctness fixture, not a balanced benchmark by itself.

### 02 — Overlapping but unrelated nodes

- `incident-node-a`: KubeNodeNotReady `[100, 280)` and TargetDown `[120, 240)`.
- `incident-node-b`: KubeNodeNotReady `[110, 260)` and TargetDown `[135, 225)`.

Both use template `node-failure`, the same namespace, the same alert names, and overlapping firing intervals. Labels explicitly distinguish node-a from node-b. There are no singleton incidents, intentionally. Joining everything by namespace or timestamp proximity would disagree with the authored oracle.

### 03 — Flapping, recovery, and an unrelated overlap

`incident-flapping` contains:

- KubeNodeNotReady `[100, 130)`.
- The same label set firing again at `[170, 195)`; the 40-second gap is explicit.
- SyntheticNodeRecovered `[200, 210)`, with severity `info`.

All three get distinct episode IDs but share one reference assignment. `incident-unrelated` is a KubePodCrashLooping episode on node-b at `[175, 215)`. The recovery signal is a modeled episode, not an implicit interpretation of `end`. No `repeat`, gap, or automatic flap configuration is needed.

### 04 — Same template, different concrete occurrences

Every incident uses `node-failure` and reuses the role `primary` locally:

- `incident-a-first`: node-a symptoms at `[100, 150)` and `[110, 140)`.
- `incident-a-second`: node-a fails separately at `[300, 360)` and `[315, 340)`.
- `incident-b`: a singleton on node-b at `[320, 350)`.

The two node-a occurrences are not flapping within one oracle incident: the authored causal model explicitly declares separate occurrences. Resource identity alone cannot recover that distinction. The third occurrence overlaps the second and provides a singleton.

### 05 — Background and singleton handling

- `incident-watchdog`: Watchdog fires at `[0, 600)`, severity `none`.
- `incident-deployment`: three payments-namespace symptoms at `[100, 250)`, `[115, 205)`, and `[130, 230)`.
- `incident-oom`: an isolated batch-namespace SyntheticContainerOOM at `[220, 240)`.

Watchdog is deliberately assigned its own reference incident in this fixture. This is an evaluation convention for this scenario, **not** a statement that background alerts always represent incidents or should always be scored this way. A benchmark choosing to exclude background activity should author a different scenario, not silently change these annotations.

### 06 — Observation order is not firing order

- `incident-node`: KubeNodeNotReady starts at 100, ends at 120, and is observed at 180. TargetDown starts at 115, ends at 155, and is observed at 115.
- `incident-network`: an unrelated signal starts at 130, ends at 160, and is observed at 135.

Historical start order is `100 → 115 → 130`; streaming release order is the episodes starting at `115 → 130 → 100`. Observation after resolution is intentional and valid. A replay system must not replace `start` with `observed_at`. This generator materializes the fields; it does not run a streaming engine or add batch jitter.

### 07 — Cascade and explicit resource change

`incident-cascade` starts at 100 and contains a network-root signal, database unavailability, API errors, and database unavailability on a replacement pod. Starts are 100, 120, 140, and 165; ends are 260, 220, 220, and 210.

The database labels explicitly change from `pod: db-1` to `pod: db-2`, with a short overlap representing a modeled handover. The shared target constrains only `namespace: payments`, allowing different nodes and pods. No topology or resource-alias mapping is inferred.

`incident-other-api` is SyntheticHighErrorRate for the reports service at `[140, 190)`, in the same namespace. Matching namespace and alert name should not substitute for the authored causal distinction. Conversely, demanding identical node/pod labels would split the authored cascade.

### 08 — Seeded timing variation

- `incident-node-a`: uniform start in `[100, 200]`; two lognormal delays and durations.
- `incident-node-b`: uniform start in `[150, 250]`; a mix of uniform and lognormal alert profiles.
- `incident-restart`: a fixed singleton at `[180, 205)`.

All lognormal medians include positive sigma values. Observation delays are explicit constants (14, 5, 20, 0, and 3 seconds), not randomized firing-start offsets. Partition sizes are always 2 + 2 + 1. Overlap is verified for seed `424242`; unbounded lognormal tails mean it is not promised for every seed.

Generate another seed into a different directory to exercise temporal variation:

```sh
python3 -m generator generate \
  --scenario examples/08-seeded-variation/scenario.yaml \
  --seed 424243 --output variation-other-seed/
```

The oracle assignments follow the authored incidents, regardless of sampled overlap. Do not alter annotations to make the timing appear easier for a grouping algorithm.

### 09 — OpenShift alert storm: 200 episodes with an explicit oracle

[Input scenario](09-openshift-alert-storm/scenario.yaml). This is a **larger grouping-quality fixture**, not a production incident trace or a throughput benchmark with millions of alerts. It exercises the current PNG renderer's 200-episode limit without changing the generator or adding automatic repetition syntax.

#### Run it

From the project root, using the Python environment with PyYAML and the optional Matplotlib dependency already available:

```sh
set -e
make validate-scenario SCENARIO=examples/09-openshift-alert-storm/scenario.yaml
make generate SCENARIO=examples/09-openshift-alert-storm/scenario.yaml SEED=424242 OUTPUT=dataset-09/
make validate-dataset OUTPUT=dataset-09/
make visualize OUTPUT=dataset-09/ PNG=timeline-09.png
# Open timeline-09.png in an image viewer and zoom in: it contains 200 rows.
```

`dataset-09/` and `timeline-09.png` must not already exist. Use `PYTHON=/path/to/python` on the Make commands if the default Python does not have the required libraries. Change `SEED` and use new output paths for another materialization. The YAML is fully expanded because the strict public schema deliberately rejects aliases and undocumented `repeat`/`count` fields.

#### Composition and reference partition

The two clusters, `synthetic-east` and `synthetic-west`, are fictitious. Hosts use the reserved `.example.invalid` domain; node, pod, deployment, job, and quota names are invented. Both clusters reuse ordinary namespace and resource names. A cluster label is a resource boundary, not an oracle ID: each cluster contains many separate incidents.

| Authored fault family | Template | Concrete incidents | Episodes each | Episodes total | Oracle convention |
|---|---|---:|---:|---:|---|
| Node outage with recurrence | `node-outage-flapping` | 10 | 5 | 50 | Two disjoint node-unready episodes, unreachable-node evidence, and two unknown/pending pod symptoms share one incident. |
| Failed multi-component rollout | `bad-rollout` | 6 | 6 | 36 | Three crash-looping pods and three stuck deployments share one release/configuration fault. |
| Filesystem exhaustion | `filesystem-exhaustion` | 5 | 6 | 30 | Two mounts on one host each emit a space forecast, a low-space warning, and a nested critical episode. |
| Network degradation | `network-degradation` | 4 | 6 | 24 | Receive/transmit errors, recurring node unavailability, and an unknown/pending pod share one network fault. |
| etcd disk latency | `etcd-disk-latency` | 2 | 8 | 16 | Disk/commit latency, failed requests, and a brief leader loss share one storage-latency incident per cluster. |
| Later etcd quorum loss | `etcd-quorum-loss` | 2 | 8 | 16 | Two unavailable control-plane nodes and surviving-member/quorum symptoms share a new, separate incident. |
| Capacity and quota pressure | `capacity-and-quota-pressure` | 4 | 5 | 20 | A demand burst produces cluster request overcommit and namespace quota pressure. |
| Isolated failed job | `isolated-job-failure` | 8 | 1 | 8 | Each failed job is an independent singleton, even when another incident overlaps it. |
| **Total** | **8 templates** | **41** | | **200** | **8 singleton incidents; no unresolved assignments.** |

The sorted partition sizes are **8 groups of 1, 14 groups of 5, 15 groups of 6, and 4 groups of 8**. Every episode receives exactly one high-confidence `synthetic-oracle` assignment. Here, high confidence means certainty about the authored partition, not evidence that the same combination would have one root cause in production.

The baseline seed `424242` produces 166 warning, 22 critical, and 12 info episodes. Its earliest firing start is 1191 seconds and its latest end is 25323 seconds; these are observed output bounds, **not** a configured generation window. There are 19 distinct alert names and both firing-time overlap and observation-order inversions. Changing the seed changes sampled times without changing the authored label/reference memberships or partition sizes.

#### What the benchmark challenges

- **Over-grouping:** distinct incidents overlap with the same cluster, namespace, and alert name. Temporal proximity or a common namespace is not enough to reproduce this oracle.
- **Under-grouping:** one authored incident can span node, pod, host-interface, deployment, or etcd symptoms with different labels, namespaces, delays, and durations.
- **Flapping versus recurrence:** node and network incidents explicitly contain two `KubeNodeNotReady` episodes with identical labels and at least a 900-second firing gap. They retain one reference assignment. Later etcd quorum losses are separate incidents from earlier disk-latency episodes, even in the same cluster.
- **Severity is not identity:** a filesystem warning and critical condition can overlap for one resource and one reference incident. The fixture includes raw firing episodes, not Alertmanager's inhibited notification stream.
- **Singleton retention:** isolated job failures must not disappear into nearby multi-alert incidents merely because they occur in `default`.
- **Arrival-order sensitivity:** fixed observation delays differ across alerts. Some short episodes are observed after they end, deliberately; this does not change their firing interval or oracle assignment.

These are intended properties of the data, not assertions about a production grouping implementation.

#### Temporal model and source-rule constraints

Incident starts use bounded uniform distributions in several waves. Alerts inherit that shared origin. Delays are fixed or bounded uniform values; durations mix fixed, uniform, and lognormal distributions, with positive sigma. Observation delays are explicit nonnegative constants. No missing observations, batch jitter, or automatic cascades are inferred.

Each configured alert delay is at least the upstream rule's pending `for` duration. This is a modest consistency check, **not** a PromQL simulator: metric thresholds, range-vector history, rule-evaluation cadence, deployment progress deadlines, request-volume gates, and alert-state transitions are not reproduced. The historical metric conditions needed by the rules are assumed. Avoid interpreting the scenario's `delay` as only scrape latency.

| Rule family used here | Pinned upstream pending period | Important interpretation |
|---|---|---|
| `KubeNodeNotReady`, `KubeNodeUnreachable`, `KubePodNotReady`, `KubePodCrashLooping`, `KubeDeploymentRolloutStuck`, `KubeJobFailed` | 15 minutes | Workload expressions are restricted to `openshift-*`, `kube-*`, or `default`; this fixture uses `default` for its invented application workloads. |
| `KubeCPUOvercommit`, `KubeMemoryOvercommit` | 10 minutes | These concern **resource requests and node-failure tolerance**, not measured CPU or memory utilization. Rules explicitly label `namespace: kube-system`; the fixture preserves that scope. |
| `KubeQuotaAlmostFull` | 15 minutes | The rule is info severity and selects quota usage greater than 90% but below 100%. This is not an exceeded-quota alert. |
| `NodeFilesystemSpaceFillingUp` | 1 hour | A free-space trend predicts exhaustion; it is not simply a current low-space threshold. |
| `NodeFilesystemAlmostOutOfSpace` | 30 minutes | Warning and critical variants have different thresholds. This fixture makes each critical interval fall inside its warning interval. |
| `NodeNetworkReceiveErrs`, `NodeNetworkTransmitErrs` | 1 hour | Sustained interface-error symptoms; not a direct measurement of a complete network partition. |
| `etcdHighFsyncDurations`, `etcdHighCommitDurations`, `etcdHighNumberOfFailedGRPCRequests` | 10 minutes | Disk/commit latency and request-failure expressions have additional history and eligibility conditions; they are assumed, not evaluated. |
| `etcdNoLeader`, `etcdInsufficientMembers`, `etcdMembersDown` | 1, 3, and 20 minutes respectively | Different symptoms can become firing at different times during one quorum failure. |

Additional source-specific cautions:

- The pinned `KubePodNotReady` expression selects `Pending|Unknown` and excludes unschedulable pods. Its broader runbook discusses readiness problems too, but this scenario's related roles explicitly model unknown/pending pods—not an automatic claim that every running pod with a failed readiness probe emits that rule.
- `KubePodCrashLooping` is **not** duplicated as `KubePodNotReady` for the same running crash-looping pod. Rollout incidents instead pair it with `KubeDeploymentRolloutStuck`, whose pinned expression checks `Progressing=false`.
- The pinned rollout rule is named `KubeDeploymentRolloutStuck`; this example does not substitute the older/different `KubeDeploymentReplicasMismatch` name from other catalogues.
- During quorum loss, `etcdNoLeader` and failed-request observations are attached to the surviving third member, not to powered-off members. Complete monitoring visibility during a real control-plane outage is nevertheless an explicit simplification.
- The pinned etcd failed-gRPC rule includes request-rate and infrastructure-provider eligibility gates. This fixture assumes an eligible environment and enough requests; it does not generate or evaluate those metrics.
- Label sets are intentionally partial, explicit synthetic representations. Rule aggregation may remove labels; in particular, cluster overcommit is not attributed to one node, and quorum summaries are not assigned a fictitious individual `instance`. The v1-required namespace for node-oriented alerts is explicitly supplied as `openshift-monitoring`, not inferred by the generator.

#### Sources and how they were used

**Release baseline:** the OpenShift operator rules below were inspected from `release-4.18` and are linked at immutable commits. They establish alert names, severities, expression scope, and pending durations. They do **not** establish the probability, frequency, correlation, or duration of production faults. Runbooks explain possible mechanisms and troubleshooting context, not unique causal proofs.

| ID | Public source | Contribution to this example |
|---|---|---|
| S1 | [OpenShift monitoring: control-plane rules](https://github.com/openshift/cluster-monitoring-operator/blob/83ca2e8cd96f4edf1cf709f9b9da6b0ec1d67db8/assets/control-plane/prometheus-rule.yaml) | Node availability, pod state, rollout, job, request-overcommit, and quota rule names, selectors, severities, and `for` periods. |
| S2 | [OpenShift monitoring: node-exporter rules](https://github.com/openshift/cluster-monitoring-operator/blob/83ca2e8cd96f4edf1cf709f9b9da6b0ec1d67db8/assets/node-exporter/prometheus-rule.yaml) | Filesystem forecasting/low-space and network-interface error rule definitions. |
| S3 | [OpenShift etcd operator: alert rules](https://github.com/openshift/cluster-etcd-operator/blob/3af8b9d6ceb707462af67ebbda92ec4c2b341d81/manifests/0000_90_etcd-operator_03_prometheusrule.yaml) | Disk/commit latency, failed gRPC requests, member loss, leadership, and quorum alert definitions. |
| S4 | [OpenShift runbook: KubeNodeNotReady](https://github.com/openshift/runbooks/blob/937cdf63cee71cacd43984f81260904cdfc998cc/alerts/cluster-monitoring-operator/KubeNodeNotReady.md) | Node unavailability and possible network-related communication failures; motivates cross-component symptoms. |
| S5 | [OpenShift runbook: KubePodNotReady](https://github.com/openshift/runbooks/blob/937cdf63cee71cacd43984f81260904cdfc998cc/alerts/cluster-monitoring-operator/KubePodNotReady.md) | Pod availability impact and diagnosis; qualified by the narrower pinned expression in S1. |
| S6 | [OpenShift runbook: NodeFilesystemSpaceFillingUp](https://github.com/openshift/runbooks/blob/937cdf63cee71cacd43984f81260904cdfc998cc/alerts/cluster-monitoring-operator/NodeFilesystemSpaceFillingUp.md) | Space-growth forecasting, possible cleanup failures, and consequences of exhausted storage. |
| S7 | [OpenShift runbook: etcdHighFsyncDurations](https://github.com/openshift/runbooks/blob/937cdf63cee71cacd43984f81260904cdfc998cc/alerts/cluster-etcd-operator/etcdHighFsyncDurations.md) | Slow/fragmented disks can impair etcd read/write latency and leadership stability. |
| S8 | [OpenShift runbook: etcdInsufficientMembers](https://github.com/openshift/runbooks/blob/937cdf63cee71cacd43984f81260904cdfc998cc/alerts/cluster-etcd-operator/etcdInsufficientMembers.md) | Multiple unavailable or disconnected control-plane nodes can prevent quorum and disrupt API operations. |

Causal assignments, fault counts, wave spacing, resource relationships, recovery order, lognormal parameters, and observation delays are **authored modeling choices**. No production data, credentials, or production-derived timing statistics were used; no runbook commands were executed against a cluster. Availability and rule definitions can differ in other OpenShift releases.

**Authoring provenance caveat:** this fixture and its documentation were assembled with AI assistance using the public sources above. The deterministic generator has no LLM client. Its existing v1 manifest/card hard-code `llm_assisted: false` / no LLM assistance and do not capture scenario-authoring provenance; those fields must not be cited as proof that this scenario was authored without AI assistance. This limitation is documented here rather than changing the generator's metadata contract in an example-only change.

#### Verification and limits

Regression checks cover exact episode/incident/template counts, partition sizes, supported alert names, minimum pending-period delays, label scope, different seeds, same-seed byte equivalence of all four artifacts, overlapping independent incidents with matching cluster/namespace/alert name, flapping gaps, late observations, and PNG decoding without modifying dataset files.

The full PNG has 200 rows and requires zooming. It is an evaluator/debugging artifact containing reference assignments, not input to a grouping algorithm. More than 200 episodes would require a different visualization strategy; this example intentionally does not relax the renderer limit. Correct synthetic reference labels and documented rule names still do not establish production-realistic timing or incident prevalence.

## Coverage boundaries

Together these examples cover delayed symptoms, independent overlap, shared namespaces, flapping/recovery, explicit resource-label change, Watchdog/restart activity, delayed observation, singletons, repeated alert names and targets, and authored cascades. Tests assert their counts, partitions, fixed intervals, overlap, and relevant order/gap properties.

Missing observations, batch jitter, empirical profiles, and automatic cascades are intentionally unsupported. Do not add undocumented fields to approximate them. None of these examples uses production-derived statistics; correct oracle assignments do not establish realistic alert timing or realistic incident prevalence.
