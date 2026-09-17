"""Causally related episode times with independent, stable random streams."""

import hashlib
import json
import math
import random

from .schema import MAX_SECONDS, fail, integer, validate_scenario


def stream(seed, *identity):
    encoded = json.dumps(
        [seed, *identity], ensure_ascii=True, separators=(",", ":")
    ).encode()
    return random.Random(int.from_bytes(hashlib.sha256(encoded).digest(), "big"))


def sample(spec, rng, field, duration=False):
    kind = spec["distribution"]
    if kind == "fixed":
        result = spec["seconds"]
    elif kind == "uniform":
        # Use only Random.random(), whose seeded sequence is stable in Python.
        low, high = spec["min_seconds"], spec["max_seconds"]
        result = low + int(rng.random() * (high - low + 1))
    else:
        # Box–Muller makes the median exp(mu), not the arithmetic mean.
        normal = math.sqrt(-2 * math.log(1 - rng.random())) * math.cos(
            2 * math.pi * rng.random()
        )
        try:
            value = math.exp(math.log(spec["median_seconds"]) + spec["sigma"] * normal)
        except OverflowError:
            fail(
                "scenario.yaml",
                field,
                "sample overflow; reduce median_seconds or sigma",
            )
        if not math.isfinite(value) or value > MAX_SECONDS:
            fail(
                "scenario.yaml",
                field,
                "sample exceeds supported seconds; reduce median_seconds or sigma",
            )
        whole = math.floor(value)
        result = whole + int(value - whole >= 0.5)
        if duration:
            result = max(1, result)
    return result


def add_seconds(left, right, field):
    result = left + right
    if result > MAX_SECONDS:
        fail(
            "scenario.yaml",
            field,
            "materialized timestamp exceeds supported seconds; reduce the time parameters",
        )
    return result


def materialize(scenario, seed):
    validate_scenario(scenario)
    integer(seed, "configuration", "seed", -(2**63), 2**63 - 1)
    episodes: list[dict] = []
    annotations: list[dict] = []
    for index, incident in enumerate(scenario["incidents"]):
        identity = (
            scenario["scenario_id"],
            incident["incident_template_id"],
            incident["reference_incident_id"],
        )
        field = f"incidents[{index}]"
        incident_start = sample(
            incident["start"],
            stream(seed, *identity, "incident-start"),
            f"{field}.start",
        )
        for alert_index, alert in enumerate(incident["alerts"]):
            af = f"{field}.alerts[{alert_index}]"
            role = alert["role"]
            delay = sample(
                alert["delay"], stream(seed, *identity, role, "delay"), f"{af}.delay"
            )
            duration = sample(
                alert["duration"],
                stream(seed, *identity, role, "duration"),
                f"{af}.duration",
                duration=True,
            )
            start = add_seconds(incident_start, delay, f"{af}.delay")
            end = add_seconds(start, duration, f"{af}.duration")
            observed_at = add_seconds(
                start,
                alert.get("observation_delay_seconds", 0),
                f"{af}.observation_delay_seconds",
            )
            # Sequential IDs expose neither a reference ID nor an incident boundary.
            episode_id = f"e-{len(episodes) + 1:06d}"
            episode_labels = {
                "alertname": alert["alertname"],
                "namespace": alert["namespace"],
                **alert.get("labels", {}),
            }
            episodes.append(
                {
                    "episode_id": episode_id,
                    "start": start,
                    "end": end,
                    "observed_at": observed_at,
                    "labels": dict(sorted(episode_labels.items())),
                }
            )
            annotations.append(
                {
                    "episode_id": episode_id,
                    "reference_incident_id": incident["reference_incident_id"],
                    "confidence": "high",
                    "source": "synthetic-oracle",
                }
            )
    # Do not leave reference-partition blocks in the algorithm input order.
    episodes.sort(key=lambda item: (item["start"], item["episode_id"]))
    # IDs reflect chronological order, not contiguous incident-definition blocks.
    old_to_new = {
        episode["episode_id"]: f"e-{index + 1:06d}"
        for index, episode in enumerate(episodes)
    }
    for episode in episodes:
        episode["episode_id"] = old_to_new[episode["episode_id"]]
    for annotation in annotations:
        annotation["episode_id"] = old_to_new[annotation["episode_id"]]
    annotations.sort(key=lambda item: item["episode_id"])
    return {"episodes": episodes}, {"annotations": annotations}
