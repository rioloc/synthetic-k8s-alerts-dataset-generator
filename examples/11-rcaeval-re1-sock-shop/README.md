# 11 — RCAEval RE1 Sock Shop metric families

[Authored scenario](scenario.yaml) · [All examples](../README.md) · [Project setup](../../README.md#how-to-use)

This fixture uses the metric vocabulary from five representative `RE1-SS`
cases for the `carts` service. It does not import metric values, source
timestamps, thresholds, or anomaly decisions.

**Expected output:** 19 episodes, 5 reference incidents; partition sizes
**3 + 4 + 4 + 4 + 4**.

## Metric definitions used

The `metric` label preserves the source column name. `SyntheticMetric*` is an
authored alert name that groups the metric columns into an alert-like signal;
it is not a claim that RCAEval or Sock Shop defines that alert rule.

| Fault family | Source case | Metric signals used |
|---|---|---|
| CPU | `RE1-SS/carts_cpu/1/simple_data.csv` | `carts_cpu`, `carts-db_cpu`, `carts_latency-90`, `carts_error` |
| MEM | `RE1-SS/carts_mem/1/simple_data.csv` | `carts_mem`, `carts-db_mem`, `carts_latency-90`, `carts_error` |
| DISK | `RE1-SS/carts_disk/1/simple_data.csv` | `carts_workload`, `carts_latency-50`, `carts_latency-90`, `orders_error` |
| DELAY | `RE1-SS/carts_delay/1/simple_data.csv` | `carts_latency-50`, `carts_latency-90`, `carts_workload` |
| LOSS | `RE1-SS/carts_loss/1/simple_data.csv` | `carts_error`, `carts_latency-50`, `carts_latency-90`, `carts_workload` |

`DISK` is a source fault family, not a direct `_disk` metric. Its scenario
uses the latency/workload/error signals available in that case. The
`orders_error` signal is an authored downstream symptom from the source metric
vocabulary, not an inferred root-cause assignment.

## Generate and validate

Run from the project root:

```sh
set -e
make validate-scenario SCENARIO=examples/11-rcaeval-re1-sock-shop/scenario.yaml
make generate SCENARIO=examples/11-rcaeval-re1-sock-shop/scenario.yaml SEED=424242 OUTPUT=dataset-11/
make validate-dataset OUTPUT=dataset-11/
```

The firing times and durations are authored relative seconds. They are not
converted from the Unix timestamps in `inject_time.txt`; the source metric
values are never read at generation time.

RCAEval is the public source catalogue: <https://github.com/phamquiluan/RCAEval>.
Its repository is MIT-licensed. Keep the local 2.4 GB checkout outside this
repository; only the metric names used by this authored fixture are recorded.
