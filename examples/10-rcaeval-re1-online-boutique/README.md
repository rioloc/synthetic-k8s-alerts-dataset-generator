# 10 — RCAEval RE1 Online Boutique metric families

[Authored scenario](scenario.yaml) · [All examples](../README.md) · [Project setup](../../README.md#how-to-use)

This fixture uses the metric vocabulary from five representative `RE1-OB`
cases for the `adservice` service. It does not import metric values, source
timestamps, thresholds, or anomaly decisions.

**Expected output:** 19 episodes, 5 reference incidents; partition sizes
**3 + 4 + 4 + 4 + 4**.

## Metric definitions used

The `metric` label preserves the source column name. `SyntheticMetric*` is an
authored alert name that groups the metric columns into an alert-like signal;
it is not a claim that RCAEval or Online Boutique defines that alert rule.

| Fault family | Source case | Metric signals used |
|---|---|---|
| CPU | `RE1-OB/adservice_cpu/1/data.csv` | `adservice_cpu`, `adservice_load`, `adservice_latency`, `adservice_mem` |
| MEM | `RE1-OB/adservice_mem/1/data.csv` | `adservice_mem`, `adservice_cpu`, `adservice_load`, `adservice_latency` |
| DISK | `RE1-OB/adservice_disk/1/data.csv` | `adservice_latency-50`, `adservice_latency-90`, `adservice_error`, `adservice_workload` |
| DELAY | `RE1-OB/adservice_delay/1/data.csv` | `adservice_latency-50`, `adservice_latency-90`, `adservice_workload` |
| LOSS | `RE1-OB/adservice_loss/1/data.csv` | `frontend_error`, `adservice_latency-50`, `adservice_latency-90`, `adservice_workload` |

`DISK` is a source fault family, not a direct `_disk` metric. Its scenario
uses the latency/error/workload signals available in that case. The `LOSS`
case uses the observed `frontend_error` signal as a propagated symptom.

## Generate and validate

Run from the project root:

```sh
set -e
make validate-scenario SCENARIO=examples/10-rcaeval-re1-online-boutique/scenario.yaml
make generate SCENARIO=examples/10-rcaeval-re1-online-boutique/scenario.yaml SEED=424242 OUTPUT=dataset-10/
make validate-dataset OUTPUT=dataset-10/
```

The firing times and durations are authored relative seconds. They are not
converted from the Unix timestamps in `inject_time.txt`; the source metric
values are never read at generation time.

RCAEval is the public source catalogue: <https://github.com/phamquiluan/RCAEval>.
Its repository is MIT-licensed. Keep the local 2.4 GB checkout outside this
repository; only the metric names used by this authored fixture are recorded.
