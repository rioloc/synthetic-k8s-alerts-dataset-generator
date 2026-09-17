import copy
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import yaml

from generator.generate import materialize, sample, stream
from generator.output import ARTIFACTS, build_artifacts, publish
from generator.schema import (
    MAX_SECONDS,
    ValidationError,
    distribution,
    load_scenario,
    read_yaml,
    validate_scenario,
)
from generator.validate import (
    quality_stats,
    validate_dataset,
    validate_manifest,
    validate_records,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def example(number):
    return next(EXAMPLES.glob(f"{number:02d}-*/scenario.yaml"))


def scenario(number=8):
    return load_scenario(example(number))[0]


def artifacts(number=8, seed=424242):
    value, raw, _ = load_scenario(example(number))
    return build_artifacts(value, seed, raw)[0]


class GeneratorTests(unittest.TestCase):
    def test_same_seed_byte_equivalence_for_every_example(self):
        for path in sorted(EXAMPLES.glob("*/scenario.yaml")):
            with self.subTest(example=path.parent.name):
                value, raw, _ = load_scenario(path)
                first, _ = build_artifacts(value, 424242, raw)
                second, _ = build_artifacts(value, 424242, raw)
                self.assertEqual(set(first), set(ARTIFACTS))
                self.assertEqual(first, second)
                with tempfile.TemporaryDirectory() as temporary:
                    output = Path(temporary) / "dataset"
                    publish(first, output)
                    validate_dataset(output)
                    self.assertEqual(
                        first,
                        {name: (output / name).read_bytes() for name in ARTIFACTS},
                    )

    def test_different_seeds_change_times_not_contract(self):
        first, first_annotations = materialize(scenario(), 424242)
        second, second_annotations = materialize(scenario(), 424243)
        self.assertNotEqual(first, second)
        for episodes, annotations in (
            (first, first_annotations),
            (second, second_annotations),
        ):
            validate_records(episodes, annotations)
            self.assertEqual(
                [item["episode_id"] for item in episodes["episodes"]],
                [f"e-{index:06d}" for index in range(1, 6)],
            )
        self.assertEqual(
            sorted(
                json.dumps(item["labels"], sort_keys=True) for item in first["episodes"]
            ),
            sorted(
                json.dumps(item["labels"], sort_keys=True)
                for item in second["episodes"]
            ),
        )

    def test_fixed_uniform_and_lognormal(self):
        fixed = {"distribution": "fixed", "seconds": 30}
        uniform = {"distribution": "uniform", "min_seconds": 10, "max_seconds": 12}
        lognormal = {"distribution": "lognormal", "median_seconds": 30, "sigma": 0.4}
        self.assertEqual(sample(fixed, stream(1), "fixed"), 30)
        rng = stream(1)
        values = [sample(uniform, rng, "uniform") for _ in range(1000)]
        self.assertEqual(set(values), {10, 11, 12})
        rng = stream(1)
        values = [sample(lognormal, rng, "lognormal") for _ in range(10000)]
        self.assertAlmostEqual(statistics.median(values), 30, delta=1)
        self.assertGreater(statistics.mean(values), 31)
        self.assertGreater(max(values) - min(values), 50)

    def test_rounding_and_minimum_duration(self):
        # cos(pi/2) is effectively zero: the draw is the configured median.
        spec = {"distribution": "lognormal", "median_seconds": 2.5, "sigma": 0.4}
        rng = Mock(random=Mock(side_effect=[0.5, 0.25]))
        self.assertEqual(sample(spec, rng, "delay"), 3)
        spec["median_seconds"] = 0.01
        self.assertEqual(sample(spec, stream(1), "delay"), 0)
        self.assertEqual(sample(spec, stream(1), "duration", duration=True), 1)

    def test_rounding_preserves_large_exact_integer_seconds(self):
        spec = {"distribution": "lognormal", "median_seconds": 30, "sigma": 0.4}
        for value in (2**52 + 1, MAX_SECONDS):
            with (
                self.subTest(value=value),
                patch("generator.generate.math.exp", return_value=float(value)),
            ):
                self.assertEqual(sample(spec, stream(1), "delay"), value)

    def test_invalid_distributions_have_field_errors(self):
        cases = [
            {},
            {"distribution": "empirical", "profile": "anything"},
            {"distribution": "other"},
            {"distribution": []},
            {"distribution": "fixed"},
            {"distribution": "fixed", "seconds": -1},
            {"distribution": "fixed", "seconds": True},
            {"distribution": "fixed", "seconds": 1.5},
            {"distribution": "fixed", "seconds": 1, "sigma": 0.4},
            {"distribution": "uniform", "min_seconds": 2, "max_seconds": 1},
            {"distribution": "uniform", "min_seconds": 1, "max_seconds": 1},
            {"distribution": "uniform", "min_seconds": -1, "max_seconds": 1},
            {"distribution": "lognormal", "median_seconds": 30},
            {"distribution": "lognormal", "median_seconds": 0, "sigma": 0.4},
            {"distribution": "lognormal", "median_seconds": 30, "sigma": 0},
            {"distribution": "lognormal", "median_seconds": 30, "sigma": -0.4},
            {"distribution": "lognormal", "median_seconds": 30, "sigma": math.inf},
            {"distribution": "lognormal", "median_seconds": math.nan, "sigma": 0.4},
        ]
        for value in cases:
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(ValidationError, r"fixture.yaml: delay"),
            ):
                distribution(value, "fixture.yaml", "delay")
        with self.assertRaises(ValidationError):
            distribution(
                {"distribution": "fixed", "seconds": 0},
                "fixture.yaml",
                "duration",
                duration=True,
            )
        with self.assertRaises(ValidationError):
            distribution(
                {"distribution": "uniform", "min_seconds": 0, "max_seconds": 2},
                "fixture.yaml",
                "duration",
                duration=True,
            )

    def test_materialized_invariants_many_seeds(self):
        for seed in range(50):
            episodes, annotations = materialize(scenario(), seed)
            validate_records(episodes, annotations)
            for episode in episodes["episodes"]:
                self.assertLess(episode["start"], episode["end"])
                self.assertGreaterEqual(episode["observed_at"], episode["start"])
                self.assertIs(type(episode["start"]), int)

    def test_reference_metadata_is_separate_and_target_not_injected(self):
        value = scenario(1)
        value["incidents"][0]["target"]["zone"] = "zone-not-an-alert-label"
        episodes, annotations = materialize(value, 1)
        encoded = json.dumps(episodes)
        self.assertNotIn("incident-node-a", encoded)
        self.assertNotIn("node-failure", encoded)
        self.assertNotIn("zone-not-an-alert-label", encoded)
        self.assertIn("incident-node-a", json.dumps(annotations))
        for episode in episodes["episodes"]:
            self.assertEqual(
                set(episode), {"episode_id", "start", "end", "observed_at", "labels"}
            )
        explicit = value["incidents"][0]["alerts"][1]
        target_down = next(
            item
            for item in episodes["episodes"]
            if item["labels"]["alertname"] == "TargetDown"
        )
        self.assertEqual(
            target_down["labels"],
            {
                "alertname": explicit["alertname"],
                "namespace": explicit["namespace"],
                **explicit["labels"],
            },
        )
        self.assertNotIn("node", target_down["labels"])

    def test_example_expected_counts_and_partitions(self):
        expected = {
            1: [3],
            2: [2, 2],
            3: [1, 3],
            4: [1, 2, 2],
            5: [1, 1, 3],
            6: [1, 2],
            7: [1, 4],
            8: [1, 2, 2],
            9: [1] * 8 + [5] * 14 + [6] * 15 + [8] * 4,
        }
        for number, sizes in expected.items():
            with self.subTest(number=number):
                value = scenario(number)
                episodes, annotations = materialize(value, 424242)
                counts: dict[str, int] = {}
                for annotation in annotations["annotations"]:
                    ref = annotation["reference_incident_id"]
                    counts[ref] = counts.get(ref, 0) + 1
                self.assertEqual(sorted(counts.values()), sizes)
                self.assertEqual(len(episodes["episodes"]), sum(sizes))
                if number != 1:
                    self.assertTrue(
                        quality_stats(episodes["episodes"], annotations["annotations"])[
                            "overlapping_incidents"
                        ]
                    )

    def test_alert_storm_rule_baseline_and_causal_structure(self):
        value = scenario(9)
        expected_templates = {
            "node-outage-flapping": 10,
            "bad-rollout": 6,
            "filesystem-exhaustion": 5,
            "network-degradation": 4,
            "etcd-disk-latency": 2,
            "etcd-quorum-loss": 2,
            "capacity-and-quota-pressure": 4,
            "isolated-job-failure": 8,
        }
        # Minimum pending periods from the pinned OpenShift 4.18 rules, not
        # production timing statistics or a reimplementation of PromQL.
        pending_seconds = {
            "KubeNodeNotReady": 900,
            "KubeNodeUnreachable": 900,
            "KubePodNotReady": 900,
            "KubePodCrashLooping": 900,
            "KubeDeploymentRolloutStuck": 900,
            "NodeFilesystemSpaceFillingUp": 3600,
            "NodeFilesystemAlmostOutOfSpace": 1800,
            "NodeNetworkReceiveErrs": 3600,
            "NodeNetworkTransmitErrs": 3600,
            "etcdHighFsyncDurations": 600,
            "etcdHighCommitDurations": 600,
            "etcdHighNumberOfFailedGRPCRequests": 600,
            "etcdNoLeader": 60,
            "etcdInsufficientMembers": 180,
            "etcdMembersDown": 1200,
            "KubeCPUOvercommit": 600,
            "KubeMemoryOvercommit": 600,
            "KubeQuotaAlmostFull": 900,
            "KubeJobFailed": 900,
        }
        actual_templates: dict[str, int] = {}
        names = set()
        for incident in value["incidents"]:
            template = incident["incident_template_id"]
            actual_templates[template] = actual_templates.get(template, 0) + 1
            for alert in incident["alerts"]:
                name = alert["alertname"]
                names.add(name)
                delay = alert["delay"]
                minimum = (
                    delay["seconds"]
                    if delay["distribution"] == "fixed"
                    else delay["min_seconds"]
                )
                self.assertGreaterEqual(minimum, pending_seconds[name], name)
                if name in ("KubeCPUOvercommit", "KubeMemoryOvercommit"):
                    self.assertEqual(alert["namespace"], "kube-system")
                    self.assertNotIn("node", alert["labels"])
                if name == "KubeQuotaAlmostFull":
                    self.assertEqual(alert["labels"]["severity"], "info")
                    self.assertEqual(alert["namespace"], "default")
                if name.startswith("etcd"):
                    self.assertEqual(alert["namespace"], "openshift-etcd")
        self.assertEqual(actual_templates, expected_templates)
        self.assertEqual(names, set(pending_seconds))

        for seed in (424242, 424243):
            episodes, annotations = materialize(value, seed)
            validate_records(episodes, annotations)
            stats = quality_stats(episodes["episodes"], annotations["annotations"])
            self.assertEqual(stats["episode_count"], 200)
            self.assertEqual(stats["incident_count"], 41)
            self.assertEqual(stats["singleton_count"], 8)
            self.assertEqual(stats["unresolved_count"], 0)
            self.assertTrue(stats["overlapping_incidents"])
            self.assertEqual(
                {item["labels"]["cluster"] for item in episodes["episodes"]},
                {"synthetic-east", "synthetic-west"},
            )
            self.assertTrue(
                any(item["observed_at"] > item["end"] for item in episodes["episodes"])
            )
            assignments = {
                item["episode_id"]: item["reference_incident_id"]
                for item in annotations["annotations"]
            }
            self.assertTrue(
                any(
                    assignments[left["episode_id"]] != assignments[right["episode_id"]]
                    and all(
                        left["labels"][key] == right["labels"][key]
                        for key in ("cluster", "namespace", "alertname")
                    )
                    and left["start"] < right["end"]
                    and right["start"] < left["end"]
                    for left in episodes["episodes"]
                    for right in episodes["episodes"]
                )
            )
            self.assertNotEqual(
                [item["episode_id"] for item in episodes["episodes"]],
                [
                    item["episode_id"]
                    for item in sorted(
                        episodes["episodes"],
                        key=lambda item: (item["observed_at"], item["episode_id"]),
                    )
                ],
            )
            for incident in value["incidents"]:
                if incident["incident_template_id"] not in (
                    "node-outage-flapping",
                    "network-degradation",
                ):
                    continue
                flaps = [
                    item
                    for item in episodes["episodes"]
                    if assignments[item["episode_id"]]
                    == incident["reference_incident_id"]
                    and item["labels"]["alertname"] == "KubeNodeNotReady"
                ]
                self.assertEqual(len(flaps), 2)
                self.assertEqual(flaps[0]["labels"], flaps[1]["labels"])
                self.assertGreaterEqual(flaps[1]["start"] - flaps[0]["end"], 900)

    def test_alert_storm_seed_changes_times_without_changing_the_oracle(self):
        first, first_annotations = materialize(scenario(9), 424242)
        second, second_annotations = materialize(scenario(9), 424243)
        self.assertNotEqual(first, second)

        def labeled_partition(episodes, annotations):
            references = {
                item["episode_id"]: item["reference_incident_id"]
                for item in annotations["annotations"]
            }
            return sorted(
                (
                    json.dumps(item["labels"], sort_keys=True),
                    references[item["episode_id"]],
                )
                for item in episodes["episodes"]
            )

        self.assertEqual(
            labeled_partition(first, first_annotations),
            labeled_partition(second, second_annotations),
        )

    def test_hand_computed_delayed_symptoms(self):
        episodes, _ = materialize(scenario(1), 424242)
        self.assertEqual(
            [
                (item["start"], item["end"], item["observed_at"])
                for item in episodes["episodes"]
            ],
            [(100, 220, 105), (120, 190, 130), (145, 235, 147)],
        )

    def test_repeated_template_has_distinct_concrete_references(self):
        value = scenario(4)
        self.assertEqual(
            len({item["incident_template_id"] for item in value["incidents"]}), 1
        )
        episodes, annotations = materialize(value, 1)
        self.assertEqual(
            len({item["reference_incident_id"] for item in annotations["annotations"]}),
            3,
        )
        self.assertEqual(len({item["episode_id"] for item in episodes["episodes"]}), 5)

    def test_flapping_has_gaps_unique_ids_and_shared_reference(self):
        episodes, annotations = materialize(scenario(3), 1)
        flaps = [
            item
            for item in episodes["episodes"]
            if item["labels"]["alertname"] == "KubeNodeNotReady"
        ]
        self.assertEqual(
            [(item["start"], item["end"]) for item in flaps], [(100, 130), (170, 195)]
        )
        self.assertNotEqual(flaps[0]["episode_id"], flaps[1]["episode_id"])
        assignments = {
            item["episode_id"]: item["reference_incident_id"]
            for item in annotations["annotations"]
        }
        self.assertEqual(
            {assignments[item["episode_id"]] for item in flaps}, {"incident-flapping"}
        )

    def test_overlapping_incidents_keep_separate_annotations(self):
        episodes, annotations = materialize(scenario(2), 1)
        assignments = {
            item["episode_id"]: item["reference_incident_id"]
            for item in annotations["annotations"]
        }
        for episode in episodes["episodes"]:
            target = episode["labels"].get("node", episode["labels"].get("instance"))
            self.assertEqual(assignments[episode["episode_id"]], f"incident-{target}")
        self.assertTrue(
            quality_stats(episodes["episodes"], annotations["annotations"])[
                "overlapping_incidents"
            ]
        )

    def test_background_is_singleton_not_an_implicit_join(self):
        episodes, annotations = materialize(scenario(5), 1)
        assignments = {
            item["episode_id"]: item["reference_incident_id"]
            for item in annotations["annotations"]
        }
        watchdog = next(
            item
            for item in episodes["episodes"]
            if item["labels"]["alertname"] == "Watchdog"
        )
        self.assertEqual((watchdog["start"], watchdog["end"]), (0, 600))
        self.assertEqual(watchdog["labels"]["severity"], "none")
        self.assertEqual(assignments[watchdog["episode_id"]], "incident-watchdog")
        self.assertEqual(list(assignments.values()).count("incident-watchdog"), 1)
        self.assertTrue(
            all(
                watchdog["start"] <= item["start"] < item["end"] <= watchdog["end"]
                for item in episodes["episodes"]
            )
        )

    def test_cascade_and_resource_churn_are_explicitly_annotated(self):
        episodes, annotations = materialize(scenario(7), 1)
        assignments = {
            item["episode_id"]: item["reference_incident_id"]
            for item in annotations["annotations"]
        }
        databases = [
            item
            for item in episodes["episodes"]
            if item["labels"]["alertname"] == "SyntheticDatabaseUnavailable"
        ]
        self.assertEqual(
            {item["labels"]["pod"] for item in databases}, {"db-1", "db-2"}
        )
        self.assertEqual(
            {assignments[item["episode_id"]] for item in databases},
            {"incident-cascade"},
        )
        api_errors = [
            item
            for item in episodes["episodes"]
            if item["labels"]["alertname"] == "SyntheticHighErrorRate"
        ]
        self.assertEqual(
            {item["labels"]["namespace"] for item in api_errors}, {"payments"}
        )
        self.assertEqual(
            {assignments[item["episode_id"]] for item in api_errors},
            {"incident-cascade", "incident-other-api"},
        )

    def test_observation_delay_reorders_arrivals_and_can_exceed_end(self):
        episodes, _ = materialize(scenario(6), 1)
        values = episodes["episodes"]
        self.assertNotEqual(
            values, sorted(values, key=lambda item: item["observed_at"])
        )
        self.assertGreater(values[0]["observed_at"], values[0]["end"])

    def test_substreams_do_not_shift_after_unrelated_change_or_reordering(self):
        original = scenario()
        before, _ = materialize(original, 42)
        changed = copy.deepcopy(original)
        changed["incidents"].reverse()
        changed["incidents"][-1]["alerts"].reverse()
        extra = copy.deepcopy(changed["incidents"][0])
        extra["reference_incident_id"] = "unrelated-new-incident"
        extra["target"] = {}
        for alert in extra["alerts"]:
            alert["labels"]["extra"] = "true"
        changed["incidents"].append(extra)
        after, _ = materialize(changed, 42)

        def without_ids(document):
            return sorted(
                json.dumps(
                    {key: value for key, value in item.items() if key != "episode_id"},
                    sort_keys=True,
                )
                for item in document["episodes"]
                if "extra" not in item["labels"]
            )

        self.assertEqual(without_ids(before), without_ids(after))

    def test_scenario_rejects_duplicates_conflicts_missing_and_unknown_fields(self):
        mutations = [
            lambda s: s.update(extra=True),
            lambda s: s.pop("scenario_id"),
            lambda s: s.update(version=0.1),
            lambda s: s["incidents"][1].update(
                reference_incident_id=s["incidents"][0]["reference_incident_id"]
            ),
            lambda s: s["incidents"][0]["alerts"][1].update(role="primary"),
            lambda s: s["incidents"][0]["alerts"][0]["labels"].update(
                node="wrong-node"
            ),
            lambda s: s["incidents"][0]["alerts"][0]["labels"].update(
                namespace="wrong-namespace"
            ),
            lambda s: s["incidents"][0]["alerts"][0].update(
                observation_delay_seconds=-1
            ),
            lambda s: s["incidents"][0]["alerts"][0].update(repeat=3),
            lambda s: s["incidents"][0]["alerts"][0]["labels"].update(severity=True),
        ]
        for mutate in mutations:
            value = scenario()
            mutate(value)
            with (
                self.subTest(mutation=mutate),
                self.assertRaisesRegex(ValidationError, "scenario.yaml:"),
            ):
                validate_scenario(value)

    def test_yaml_rejects_duplicates_aliases_unsafe_tags_and_multiple_documents(self):
        cases = [
            "scenario_id: first\nscenario_id: second\n",
            "labels:\n  node: a\n  node: b\n",
            "a: &shared [1]\nb: *shared\n",
            "a: !!python/object:builtins.object {}\n",
            "a: 1\n---\na: 2\n",
            "true: 1\n",
            "a: {<<: {b: 1}}\n",
            "start: 2025-99-99\n",
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "scenario.yaml"
            for content in cases:
                with self.subTest(content=content):
                    path.write_text(content)
                    with self.assertRaisesRegex(ValidationError, "scenario.yaml:"):
                        read_yaml(path)

    def test_large_yaml_integer_reports_validation_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "scenario.yaml"
            path.write_text("seed: " + "9" * 5000 + "\n")
            # Older Python versions may parse this successfully; scenario validation
            # must still reject it rather than a parser exception escaping the CLI.
            with self.assertRaisesRegex(ValidationError, "scenario.yaml:"):
                load_scenario(path)

    def test_record_validation_catches_duplicates_dangling_missing_and_times(self):
        edits = [
            lambda e, a: e["episodes"].append(copy.deepcopy(e["episodes"][0])),
            lambda e, a: a["annotations"].append(copy.deepcopy(a["annotations"][0])),
            lambda e, a: a["annotations"][0].update(episode_id="nonexistent"),
            lambda e, a: a["annotations"].pop(),
            lambda e, a: e["episodes"][0].update(end=e["episodes"][0]["start"]),
            lambda e, a: e["episodes"][0].update(
                observed_at=e["episodes"][0]["start"] - 1
            ),
            lambda e, a: e["episodes"][0].update(start=True),
            lambda e, a: e["episodes"][0].pop("start"),
            lambda e, a: e["episodes"][0]["labels"].pop("alertname"),
            lambda e, a: e["episodes"][0].update(reference_incident_id="answer"),
        ]
        for edit in edits:
            episodes, annotations = materialize(scenario(), 1)
            edit(episodes, annotations)
            with (
                self.subTest(edit=edit),
                self.assertRaisesRegex(
                    ValidationError, r"(episodes|annotations).yaml:"
                ),
            ):
                validate_records(episodes, annotations)
        for key in (
            "reference_incident_id",
            "incident_template_id",
            "confidence",
            "source",
            "role",
            "generator_extra",
            "annotation_extra",
        ):
            episodes, annotations = materialize(scenario(), 1)
            episodes["episodes"][0]["labels"][key] = "forbidden"
            with (
                self.subTest(key=key),
                self.assertRaisesRegex(ValidationError, "metadata is forbidden"),
            ):
                validate_records(episodes, annotations)

    def test_historical_records_may_omit_observed_at(self):
        episodes, annotations = materialize(scenario(), 1)
        for episode in episodes["episodes"]:
            del episode["observed_at"]
        validate_records(episodes, annotations)

    def test_quality_warnings_and_half_open_overlap(self):
        episodes, annotations = materialize(scenario(2), 1)
        for index, episode in enumerate(episodes["episodes"]):
            episode.update(
                start=index * 10, end=(index + 1) * 10, observed_at=index * 10
            )
        warnings = validate_records(episodes, annotations)
        self.assertTrue(any("no overlapping" in warning for warning in warnings))
        self.assertTrue(any("no duration variation" in warning for warning in warnings))
        self.assertTrue(any("no singleton" in warning for warning in warnings))
        for episode in episodes["episodes"]:
            episode.update(start=0, end=10, observed_at=0)
        for annotation in annotations["annotations"]:
            annotation.update(
                reference_incident_id="unknown",
                confidence="low",
                source="expert-review",
            )
        warnings = validate_records(episodes, annotations)
        self.assertTrue(any("high unresolved" in warning for warning in warnings))
        self.assertTrue(any("same time" in warning for warning in warnings))

    def test_overflow_is_actionable_and_zero_seed_is_valid(self):
        value = scenario(1)
        value["incidents"][0]["start"]["seconds"] = MAX_SECONDS
        with self.assertRaisesRegex(ValidationError, "timestamp exceeds"):
            materialize(value, 0)
        spec = {"distribution": "lognormal", "median_seconds": 30, "sigma": 10000}
        with self.assertRaisesRegex(ValidationError, "overflow"):
            sample(spec, Mock(random=Mock(side_effect=[0.5, 0])), "duration")
        materialize(scenario(1), 0)
        for seed in (True, 2**63, -(2**63) - 1):
            with self.assertRaisesRegex(ValidationError, "seed"):
                materialize(scenario(1), seed)

    def test_manifest_and_quality_card(self):
        generated = artifacts()
        manifest = yaml.safe_load(generated["manifest.yaml"])
        episodes = yaml.safe_load(generated["episodes.yaml"])["episodes"]
        annotations = yaml.safe_load(generated["annotations.yaml"])["annotations"]
        self.assertEqual(manifest["seed"], 424242)
        self.assertEqual(manifest["time_unit"], "seconds")
        self.assertEqual(manifest["episode_count"], 5)
        self.assertIn(
            b"Production-derived statistics used: **no**", generated["dataset-card.md"]
        )
        self.assertIn(
            b"without production-realistic timing", generated["dataset-card.md"]
        )
        for key, replacement in (
            ("episode_count", 99),
            ("seed", True),
            ("source_type", "production"),
            ("scenario_sha256", "bad"),
        ):
            changed = {**manifest, key: replacement}
            with self.subTest(key=key), self.assertRaises(ValidationError):
                validate_manifest(changed, episodes, annotations)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "dataset"
            publish(generated, output)
            (output / "dataset-card.md").write_text("")
            with self.assertRaisesRegex(ValidationError, "quality card is empty"):
                validate_dataset(output)

    def test_publication_refuses_existing_and_cleans_up_failures(self):
        generated = artifacts(1)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "dataset"
            output.mkdir()
            marker = output / "user-work.txt"
            marker.write_text("preserve me")
            with self.assertRaisesRegex(ValidationError, "already exists"):
                publish(generated, output)
            self.assertEqual(marker.read_text(), "preserve me")
            for operation in ("os.fsync", "os.replace"):
                with self.subTest(operation=operation):
                    destination = Path(temporary) / "failed"
                    with patch(
                        f"generator.output.{operation}",
                        side_effect=OSError("injected disk failure"),
                    ):
                        with self.assertRaisesRegex(
                            ValidationError, "injected disk failure"
                        ):
                            publish(generated, destination)
                    self.assertFalse(destination.exists())
                    self.assertEqual(
                        sorted(path.name for path in Path(temporary).iterdir()),
                        ["dataset"],
                    )

    def test_concurrent_cli_publication_preserves_one_complete_dataset(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "dataset"
            command = [
                sys.executable,
                "-m",
                "generator",
                "generate",
                "--scenario",
                str(example(8)),
                "--seed",
                "424242",
                "--output",
                str(output),
            ]
            processes = [
                subprocess.Popen(
                    command,
                    cwd=ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for _ in range(2)
            ]
            results = [process.communicate(timeout=20) for process in processes]
            self.assertEqual(
                sorted(process.returncode for process in processes), [0, 1], results
            )
            validate_dataset(output)
            self.assertEqual(
                {name: (output / name).read_bytes() for name in ARTIFACTS}, artifacts()
            )
            self.assertEqual(
                [path.name for path in Path(temporary).iterdir()], ["dataset"]
            )

    def test_cli_generation_validation_and_process_determinism(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for name, hash_seed in (("first", "1"), ("second", "999")):
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "generator",
                        "generate",
                        "--scenario",
                        str(example(8)),
                        "--seed",
                        "424242",
                        "--output",
                        str(base / name),
                    ],
                    cwd=ROOT,
                    env={**os.environ, "PYTHONHASHSEED": hash_seed},
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
            for name in ARTIFACTS:
                self.assertEqual(
                    (base / "first" / name).read_bytes(),
                    (base / "second" / name).read_bytes(),
                )
            for option, target in (
                ("--scenario", example(8)),
                ("--dataset", base / "first"),
            ):
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "generator",
                        "validate",
                        option,
                        str(target),
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
            invalid = base / "invalid.yaml"
            invalid.write_text("scenario_id: bad\nversion: '0.1'\nincidents: []\n")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "generator",
                    "generate",
                    "--scenario",
                    str(invalid),
                    "--seed",
                    "1",
                    "--output",
                    str(base / "bad"),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 1)
            self.assertIn(f"{invalid}: incidents:", completed.stderr)
            self.assertFalse((base / "bad").exists())
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "generator",
                    "generate",
                    "--scenario",
                    str(example(1)),
                    "--output",
                    str(base / "no-seed"),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("--seed", completed.stderr)


if __name__ == "__main__":
    unittest.main()
