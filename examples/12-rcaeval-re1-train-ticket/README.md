# 12 — RCAEval RE1 Train Ticket metric families

[Authored scenario](scenario.yaml) · [All examples](../README.md) · [Project setup](../../README.md#how-to-use)

This fixture uses the metric vocabulary from five representative `RE1-TT`
cases for the `ts-auth-service` service. It does not import metric values,
source timestamps, thresholds, or anomaly decisions.

**Expected output:** 19 episodes, 5 reference incidents; partition sizes
**3 + 4 + 4 + 4 + 4**.

## Metric definitions used

The `metric` label preserves the source column name. `SyntheticMetric*` is an
authored alert name that groups the metric columns into an alert-like signal;
it is not a claim that RCAEval or Train Ticket defines that alert rule.

| Fault family | Source case | Metric signals used |
|---|---|---|
| CPU | `RE1-TT/ts-auth-service_cpu/1/simple_data.csv` | `ts-auth-service_cpu`, `ts-auth-service_workload`, `ts-auth-service_latency-50`, `ts-auth-service_latency-90` |
| MEM | `RE1-TT/ts-auth-service_mem/1/simple_data.csv` | `ts-auth-service_mem`, `ts-auth-service_cpu`, `ts-auth-service_latency-50`, `ts-auth-service_latency-90` |
| DISK | `RE1-TT/ts-auth-service_disk/1/simple_data.csv` | `ts-auth-service_workload`, `ts-auth-service_latency-50`, `ts-auth-service_latency-90`, `ts-assurance-service_error` |
| DELAY | `RE1-TT/ts-auth-service_delay/1/simple_data.csv` | `ts-auth-service_latency-50`, `ts-auth-service_latency-90`, `ts-auth-service_workload` |
| LOSS | `RE1-TT/ts-auth-service_loss/1/simple_data.csv` | `ts-admin-basic-info-service_error`, `ts-auth-service_latency-50`, `ts-auth-service_latency-90`, `ts-auth-service_workload` |

`DISK` is a source fault family, not a direct `_disk` metric. Its scenario
uses the latency/workload/error signals available in that case. The
cross-service error signals are authored downstream symptoms from the source
metric vocabulary, not inferred root-cause assignments.

## Generate and validate

Run from the project root:

```sh
set -e
make validate-scenario SCENARIO=examples/12-rcaeval-re1-train-ticket/scenario.yaml
make generate SCENARIO=examples/12-rcaeval-re1-train-ticket/scenario.yaml SEED=424242 OUTPUT=dataset-12/
make validate-dataset OUTPUT=dataset-12/
```

The firing times and durations are authored relative seconds. They are not
converted from the Unix timestamps in `inject_time.txt`; the source metric
values are never read at generation time.

RCAEval is the public source catalogue: <https://github.com/phamquiluan/RCAEval>.
Its repository is MIT-licensed. Keep the local 2.4 GB checkout outside this
repository; only the metric names used by this authored fixture are recorded.
