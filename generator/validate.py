"""Validation of algorithm input and separately supplied reference annotations."""

import heapq
import re
from pathlib import Path

from . import FORMAT_VERSION, __version__
from .schema import (
    fail,
    identifier,
    integer,
    labels,
    mapping,
    read_yaml,
    sequence,
    text,
)

CONFIGURATION = {
    "time_rounding": "nearest-second-half-up",
    "minimum_duration_seconds": 1,
    "uniform_sampling": "inclusive-integer-seconds",
    "observation_delay_default_seconds": 0,
}
UNRESOLVED = frozenset({"unknown", "ambiguous"})


def quality_stats(episodes, annotations):
    assignments = {
        item["episode_id"]: item["reference_incident_id"] for item in annotations
    }
    counts: dict[str, int] = {}
    unresolved = 0
    for episode in episodes:
        reference = assignments[episode["episode_id"]]
        if reference in UNRESOLVED:
            unresolved += 1
        else:
            counts[reference] = counts.get(reference, 0) + 1
    active: list[tuple[int, str]] = []
    active_counts: dict[str, int] = {}
    overlap = False
    for episode in sorted(
        episodes, key=lambda item: (item["start"], item["episode_id"])
    ):
        while active and active[0][0] <= episode["start"]:
            _, reference = heapq.heappop(active)
            active_counts[reference] -= 1
            if active_counts[reference] == 0:
                del active_counts[reference]
        reference = assignments[episode["episode_id"]]
        if reference in UNRESOLVED:
            continue
        if active_counts and (len(active_counts) > 1 or reference not in active_counts):
            overlap = True
        heapq.heappush(active, (episode["end"], reference))
        active_counts[reference] = active_counts.get(reference, 0) + 1
    return {
        "episode_count": len(episodes),
        "incident_count": len(counts),
        "singleton_count": sum(count == 1 for count in counts.values()),
        "overlapping_incidents": overlap,
        "unresolved_count": unresolved,
    }


def validate_records(episode_document, annotation_document, directory="."):
    ef = str(Path(directory) / "episodes.yaml")
    af = str(Path(directory) / "annotations.yaml")
    mapping(episode_document, ("episodes",), (), ef, "$")
    mapping(annotation_document, ("annotations",), (), af, "$")
    episodes = sequence(episode_document["episodes"], ef, "episodes")
    annotations = sequence(annotation_document["annotations"], af, "annotations")
    ids = set()
    for index, episode in enumerate(episodes):
        field = f"episodes[{index}]"
        mapping(
            episode,
            ("episode_id", "start", "end", "labels"),
            ("observed_at",),
            ef,
            field,
        )
        eid = identifier(episode["episode_id"], ef, f"{field}.episode_id")
        if eid in ids:
            fail(ef, f"{field}.episode_id", "duplicate episode ID")
        ids.add(eid)
        start = integer(episode["start"], ef, f"{field}.start")
        end = integer(episode["end"], ef, f"{field}.end")
        if start >= end:
            fail(ef, field, "start must be less than end")
        if "observed_at" in episode:
            observed = integer(episode["observed_at"], ef, f"{field}.observed_at")
            if observed < start:
                fail(
                    ef, f"{field}.observed_at", "must be greater than or equal to start"
                )
        values = labels(episode["labels"], ef, f"{field}.labels")
        for required in ("alertname", "namespace"):
            if required not in values:
                fail(ef, f"{field}.labels.{required}", "required label is missing")
            text(values[required], ef, f"{field}.labels.{required}")
    assigned = set()
    for index, annotation in enumerate(annotations):
        field = f"annotations[{index}]"
        mapping(
            annotation,
            ("episode_id", "reference_incident_id", "confidence", "source"),
            ("note",),
            af,
            field,
        )
        eid = identifier(annotation["episode_id"], af, f"{field}.episode_id")
        if eid not in ids:
            fail(
                af,
                f"{field}.episode_id",
                "references a nonexistent episode; supply a matching episode ID",
            )
        if eid in assigned:
            fail(af, f"{field}.episode_id", "duplicate annotation assignment")
        assigned.add(eid)
        identifier(
            annotation["reference_incident_id"], af, f"{field}.reference_incident_id"
        )
        if annotation["confidence"] not in ("high", "medium", "low"):
            fail(af, f"{field}.confidence", "expected high, medium or low")
        text(annotation["source"], af, f"{field}.source")
        if "note" in annotation:
            text(annotation["note"], af, f"{field}.note")
    if ids - assigned:
        fail(
            af,
            "annotations",
            f"missing assignment for {sorted(ids - assigned)[0]}; use an explicit unknown assignment if unresolved",
        )
    stats = quality_stats(episodes, annotations)
    warnings = []
    if stats["incident_count"] == 1:
        warnings.append(f"{af}: annotations: only one resolved incident")
    if not stats["overlapping_incidents"]:
        warnings.append(f"{ef}: episodes: no overlapping independent incidents")
    if not stats["singleton_count"]:
        warnings.append(f"{af}: annotations: no singleton incidents")
    if len({episode["start"] for episode in episodes}) == 1:
        warnings.append(f"{ef}: episodes[].start: every alert starts at the same time")
    if len({episode["end"] - episode["start"] for episode in episodes}) == 1:
        warnings.append(f"{ef}: episodes: no duration variation")
    if stats["unresolved_count"] / len(episodes) > 0.1:
        warnings.append(
            f"{af}: annotations: high unresolved annotation count ({stats['unresolved_count']}/{len(episodes)}, over 10%)"
        )
    return warnings


def validate_manifest(manifest, episodes, annotations, file="manifest.yaml"):
    required = (
        "dataset_id",
        "format_version",
        "generator_version",
        "seed",
        "scenario_id",
        "scenario_version",
        "scenario_sha256",
        "time_unit",
        "source_type",
        "annotation_version",
        "llm_assisted",
        "configuration",
        "episode_count",
        "incident_count",
    )
    mapping(manifest, required, (), file, "$")
    for key in ("format_version", "scenario_version", "annotation_version"):
        if manifest[key] != FORMAT_VERSION:
            fail(file, key, f'unsupported version; expected "{FORMAT_VERSION}"')
    if manifest["generator_version"] != __version__:
        fail(
            file,
            "generator_version",
            f"unsupported generator version; expected {__version__}",
        )
    seed = integer(manifest["seed"], file, "seed", -(2**63), 2**63 - 1)
    scenario_id = identifier(manifest["scenario_id"], file, "scenario_id")
    if manifest["dataset_id"] != f"{scenario_id}-seed-{seed}":
        fail(file, "dataset_id", "must equal <scenario_id>-seed-<seed>")
    digest = text(manifest["scenario_sha256"], file, "scenario_sha256")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        fail(
            file,
            "scenario_sha256",
            "expected a lowercase SHA-256 digest of the authored input bytes",
        )
    if manifest["time_unit"] != "seconds":
        fail(file, "time_unit", "only seconds are supported")
    if (
        manifest["source_type"] != "synthetic-oracle"
        or manifest["llm_assisted"] is not False
    ):
        fail(
            file,
            "source_type/llm_assisted",
            "v1 manifests describe non-LLM synthetic-oracle datasets only",
        )
    mapping(manifest["configuration"], tuple(CONFIGURATION), (), file, "configuration")
    for key, value in CONFIGURATION.items():
        if (
            type(manifest["configuration"][key]) is not type(value)
            or manifest["configuration"][key] != value
        ):
            fail(
                file,
                f"configuration.{key}",
                f"unsupported configuration; expected {value!r}",
            )
    stats = quality_stats(episodes, annotations)
    for key in ("episode_count", "incident_count"):
        integer(manifest[key], file, key)
        if manifest[key] != stats[key]:
            fail(file, key, f"does not match the materialized records ({stats[key]})")


def validate_dataset(directory):
    directory = Path(directory)
    episodes, _ = read_yaml(directory / "episodes.yaml")
    annotations, _ = read_yaml(directory / "annotations.yaml")
    manifest, _ = read_yaml(directory / "manifest.yaml")
    warnings = validate_records(episodes, annotations, directory)
    validate_manifest(
        manifest,
        episodes["episodes"],
        annotations["annotations"],
        str(directory / "manifest.yaml"),
    )
    # ponytail: check card presence, not prose; add structured card fields if consumers need semantic checks.
    card = directory / "dataset-card.md"
    try:
        content = card.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        fail(card, "$", str(exc))
    if not content.strip():
        fail(card, "$", "quality card is empty")
    return warnings
