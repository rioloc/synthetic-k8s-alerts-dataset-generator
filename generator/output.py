"""Deterministic artifact rendering and publication of a complete dataset."""

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

import yaml

from . import FORMAT_VERSION, __version__
from .generate import materialize
from .schema import MAX_FILE_BYTES, fail, validate_scenario
from .validate import CONFIGURATION, quality_stats, validate_manifest, validate_records

ARTIFACTS = ("episodes.yaml", "annotations.yaml", "manifest.yaml", "dataset-card.md")


def render_card(scenario, manifest, episodes, annotations, warnings):
    stats = quality_stats(episodes, annotations)
    lines = [
        "# Synthetic alert dataset quality card",
        "",
        f"- Dataset: `{manifest['dataset_id']}`",
        f"- Format / annotation version: `{FORMAT_VERSION}` / `{FORMAT_VERSION}`",
        f"- Generator version: `{__version__}`",
        f"- Seed: `{manifest['seed']}`",
        f"- Scenario list: `{scenario['scenario_id']}` (version `{scenario['version']}`)",
        f"- Scenario SHA-256: `{manifest['scenario_sha256']}`",
        f"- Episode count: {stats['episode_count']}",
        f"- Reference incident count: {stats['incident_count']}",
        "",
        "## Distributions and observation timing",
        "",
        "Integer seconds; inclusive integer uniform sampling. Lognormal samples round",
        "to nearest second (half up); positive durations have a one-second minimum.",
        "",
    ]
    for incident in scenario["incidents"]:
        reference = incident["reference_incident_id"]
        start = json.dumps(incident["start"], sort_keys=True)
        lines.append(
            f"- `{reference}` / `{incident['incident_template_id']}` start: `{start}`"
        )
        for alert in incident["alerts"]:
            delay = json.dumps(alert["delay"], sort_keys=True)
            duration = json.dumps(alert["duration"], sort_keys=True)
            lines.append(
                f"  - `{alert['role']}` delay: `{delay}`; duration: `{duration}`; observation delay: fixed {alert.get('observation_delay_seconds', 0)} seconds."
            )
    lines += [
        "",
        "Observation/batch jitter: none (unsupported). Missing observations: none (unsupported).",
        "",
        "## Scenario coverage",
        "",
        f"- Independent incident overlap: {'yes' if stats['overlapping_incidents'] else 'no'} (actual half-open firing intervals).",
        f"- Singleton incident count: {stats['singleton_count']}",
        "- Alert names: "
        + ", ".join(
            f"`{name}`"
            for name in sorted({episode["labels"]["alertname"] for episode in episodes})
        ),
        "- Templates: "
        + ", ".join(
            f"`{name}`"
            for name in sorted(
                {incident["incident_template_id"] for incident in scenario["incidents"]}
            )
        ),
        "- Repetition/flapping: explicit alert definitions only; no automatic repetition or recovery inference.",
        "",
        "## Validation results",
        "",
        "Schema and semantic validation: PASS (scenario, episodes, annotations, manifest).",
        f"Warnings: {len(warnings)}.",
    ]
    lines += [f"- {warning}" for warning in warnings] or ["- None."]
    lines += [
        "",
        "## Annotation provenance and confidence",
        "",
        "- Source: synthetic-oracle; all assignments come from the authored causal scenario, not a grouping algorithm.",
        "- Confidence: high for every generated assignment; this measures certainty about the authored oracle only.",
        f"- Unresolved or ambiguous episode count: {stats['unresolved_count']}.",
        "- LLM assistance: no.",
        "",
        "## Realism limitations",
        "",
        "A synthetic oracle can have correct reference labels without production-realistic timing.",
        "Production-derived statistics used: **no**. These distributions are illustrative, not calibrated.",
        "Alert names and labels are syntactically checked, not checked against production alert rules.",
        "Starts share a sampled incident origin; remaining role-specific draws are independent conditional on that origin.",
        "Observation delay can extend beyond episode end. Replay engines and batch scheduling are not included.",
        "No empirical profiles, missing samples, automatic label churn, automatic cascades, time windows/censoring, or Prometheus exporter.",
        "Target consistency checks compare equal label keys only; no node/instance alias or topology inference.",
        "Keep the authored scenario alongside archived artifacts: its digest is recorded, but its contents are not embedded in the manifest.",
        "",
    ]
    return "\n".join(lines).encode("utf-8")


def build_artifacts(scenario, seed, scenario_bytes):
    warnings = validate_scenario(scenario, "scenario.yaml")
    episode_doc, annotation_doc = materialize(scenario, seed)
    warnings += validate_records(episode_doc, annotation_doc)
    warnings = sorted(set(warnings))
    episodes, annotations = episode_doc["episodes"], annotation_doc["annotations"]
    stats = quality_stats(episodes, annotations)
    manifest = {
        "dataset_id": f"{scenario['scenario_id']}-seed-{seed}",
        "format_version": FORMAT_VERSION,
        "generator_version": __version__,
        "seed": seed,
        "scenario_id": scenario["scenario_id"],
        "scenario_version": scenario["version"],
        "scenario_sha256": hashlib.sha256(scenario_bytes).hexdigest(),
        "time_unit": "seconds",
        "source_type": "synthetic-oracle",
        "annotation_version": FORMAT_VERSION,
        "llm_assisted": False,
        "configuration": dict(CONFIGURATION),
        "episode_count": stats["episode_count"],
        "incident_count": stats["incident_count"],
    }
    validate_manifest(manifest, episodes, annotations)
    artifacts = {}
    for name, document in zip(ARTIFACTS[:3], (episode_doc, annotation_doc, manifest)):
        data = yaml.safe_dump(
            document, sort_keys=False, allow_unicode=True, width=1000
        ).encode("utf-8")
        if len(data) > MAX_FILE_BYTES:
            fail(
                name,
                "$",
                f"generated file exceeds {MAX_FILE_BYTES} bytes; split the scenario",
            )
        artifacts[name] = data
    artifacts["dataset-card.md"] = render_card(
        scenario, manifest, episodes, annotations, warnings
    )
    return artifacts, warnings


def publish(artifacts, output):
    output = Path(output).absolute()
    if set(artifacts) != set(ARTIFACTS):
        fail(output, "$", "publication requires exactly the four canonical artifacts")
    if os.path.lexists(output):
        fail(
            output,
            "$",
            "output already exists; choose a new directory to preserve archived datasets",
        )
    stage = None
    reserved = False
    try:
        stage = Path(tempfile.mkdtemp(prefix=".generator-", dir=output.parent))
        for name in ARTIFACTS:
            with (stage / name).open("xb") as stream:
                stream.write(artifacts[name])
                stream.flush()
                os.fsync(stream.fileno())
        # mkdir is an exclusive reservation: concurrent generators cannot replace
        # one another's output. Until rename, only an empty directory is visible.
        output.mkdir()
        reserved = True
        os.replace(stage, output)
        stage = None
        reserved = False
    except OSError as exc:
        fail(output, "$", f"cannot publish dataset: {exc}")
    finally:
        if stage is not None:
            shutil.rmtree(stage)
        if reserved:
            output.rmdir()  # Only our empty reservation, never existing user data.
