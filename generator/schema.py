"""Strict, deliberately small YAML contract and scenario validation."""

import math
import re
from pathlib import Path

import yaml

from . import FORMAT_VERSION

MAX_SECONDS = 2**53 - 1
MAX_FILE_BYTES = 8 * 1024 * 1024
RESERVED_LABELS = frozenset(
    {
        "episode_id",
        "reference_incident_id",
        "incident_template_id",
        "confidence",
        "source",
        "source_type",
        "annotation_version",
        "annotation_confidence",
        "annotation_source",
        "scenario_id",
        "seed",
        "role",
        "target",
        "delay",
        "duration",
        "distribution",
        "start",
        "end",
        "observed_at",
        "observation_delay_seconds",
        "occurrence_index",
        "generator_version",
        "generator_config",
        "note",
        "seconds",
        "min_seconds",
        "max_seconds",
        "median_seconds",
        "sigma",
        "profile",
        "processing",
        "window",
        "time_unit",
    }
)
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
LABEL_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


class ValidationError(ValueError):
    """An actionable file/field validation failure."""


def fail(file, field, message):
    raise ValidationError(f"{file}: {field}: {message}")


class StrictLoader(yaml.SafeLoader):
    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            event = self.peek_event()
            raise yaml.constructor.ConstructorError(
                None,
                None,
                "YAML aliases are unsupported; write explicit values",
                event.start_mark,
            )
        return super().compose_node(parent, index)

    def construct_mapping(self, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise yaml.constructor.ConstructorError(
                    None,
                    None,
                    "mapping keys must be strings",
                    key_node.start_mark,
                )
            if key in mapping:
                raise yaml.constructor.ConstructorError(
                    None,
                    None,
                    f"duplicate key {key!r}",
                    key_node.start_mark,
                )
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def read_yaml(path):
    path = Path(path)
    try:
        with path.open("rb") as stream:
            data = stream.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            fail(path, "$", f"file exceeds {MAX_FILE_BYTES} bytes")
        value = yaml.load(data.decode("utf-8"), Loader=StrictLoader)
    except (OSError, UnicodeError) as exc:
        fail(path, "$", str(exc))
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        location = f"line {mark.line + 1}, column {mark.column + 1}" if mark else "$"
        fail(path, location, getattr(exc, "problem", None) or "invalid YAML")
    except RecursionError:
        fail(path, "$", "YAML nesting is too deep")
    except ValidationError:
        raise
    except (ValueError, OverflowError):
        fail(path, "$", "invalid YAML scalar; check numeric limits and date values")
    return value, data


def mapping(value, required, optional, file, field):
    if not isinstance(value, dict):
        fail(file, field, "expected a mapping")
    for key in sorted(set(value) - set(required) - set(optional)):
        fail(
            file,
            f"{field}.{key}",
            "unsupported field; remove it or use a documented field",
        )
    for key in required:
        if key not in value:
            fail(file, f"{field}.{key}", "required field is missing")
    return value


def text(value, file, field, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        fail(
            file,
            field,
            "expected a nonempty string" if not allow_empty else "expected a string",
        )
    return value


def identifier(value, file, field):
    text(value, file, field)
    if not ID_PATTERN.fullmatch(value):
        fail(
            file,
            field,
            "use 1–128 ASCII letters, digits, '.', '_' or '-', starting with a letter or digit",
        )
    return value


def integer(value, file, field, minimum=0, maximum=MAX_SECONDS):
    if type(value) is not int or not minimum <= value <= maximum:
        fail(file, field, f"expected an integer in [{minimum}, {maximum}]")
    return value


def sequence(value, file, field, nonempty=True):
    if not isinstance(value, list) or (nonempty and not value):
        fail(file, field, "expected a nonempty list" if nonempty else "expected a list")
    return value


def labels(value, file, field, algorithm=True):
    if not isinstance(value, dict):
        fail(file, field, "expected a string-to-string mapping")
    for key, item in value.items():
        if (
            not isinstance(key, str)
            or not LABEL_PATTERN.fullmatch(key)
            or key.startswith("__")
        ):
            fail(
                file,
                field,
                f"invalid label key {key!r}; use ordinary Prometheus-style label names",
            )
        if algorithm and (
            key in RESERVED_LABELS
            or key.startswith(("reference_", "annotation_", "generator_"))
        ):
            fail(
                file,
                f"{field}.{key}",
                "reference or generator metadata is forbidden in algorithm labels",
            )
        text(item, file, f"{field}.{key}", allow_empty=True)
    return value


def distribution(value, file, field, duration=False):
    if not isinstance(value, dict) or "distribution" not in value:
        fail(file, f"{field}.distribution", "required distribution mapping is missing")
    kind = value["distribution"]
    if not isinstance(kind, str) or kind not in ("fixed", "uniform", "lognormal"):
        fail(
            file,
            f"{field}.distribution",
            "unsupported distribution; choose fixed, uniform or lognormal (empirical profiles are not implemented)",
        )
    parameters = {
        "fixed": ("seconds",),
        "uniform": ("min_seconds", "max_seconds"),
        "lognormal": ("median_seconds", "sigma"),
    }[kind]
    mapping(value, ("distribution", *parameters), (), file, field)
    minimum = 1 if duration else 0
    if kind == "fixed":
        integer(value["seconds"], file, f"{field}.seconds", minimum)
    elif kind == "uniform":
        low = integer(value["min_seconds"], file, f"{field}.min_seconds", minimum)
        high = integer(value["max_seconds"], file, f"{field}.max_seconds", minimum)
        if low >= high:
            fail(
                file,
                field,
                "min_seconds must be less than max_seconds; use fixed for a constant",
            )
    else:
        for key in parameters:
            number = value[key]
            if (
                type(number) not in (int, float)
                or not 0 < number <= MAX_SECONDS
                or not math.isfinite(number)
            ):
                fail(file, f"{field}.{key}", "expected a finite positive number")
    return value


def validate_scenario(scenario, file="scenario.yaml"):
    mapping(scenario, ("scenario_id", "version", "incidents"), (), file, "$")
    identifier(scenario["scenario_id"], file, "scenario_id")
    if scenario["version"] != FORMAT_VERSION:
        fail(file, "version", f'expected quoted format version "{FORMAT_VERSION}"')
    incidents = sequence(scenario["incidents"], file, "incidents")
    seen = set()
    for index, incident in enumerate(incidents):
        field = f"incidents[{index}]"
        mapping(
            incident,
            ("incident_template_id", "reference_incident_id", "start", "alerts"),
            ("target",),
            file,
            field,
        )
        identifier(
            incident["incident_template_id"], file, f"{field}.incident_template_id"
        )
        reference = identifier(
            incident["reference_incident_id"], file, f"{field}.reference_incident_id"
        )
        if reference in ("unknown", "ambiguous") or reference in seen:
            fail(
                file,
                f"{field}.reference_incident_id",
                "duplicate or reserved reference ID; each concrete incident needs its own ID",
            )
        seen.add(reference)
        target = labels(
            incident.get("target", {}), file, f"{field}.target", algorithm=False
        )
        distribution(incident["start"], file, f"{field}.start")
        roles = set()
        for alert_index, alert in enumerate(
            sequence(incident["alerts"], file, f"{field}.alerts")
        ):
            af = f"{field}.alerts[{alert_index}]"
            mapping(
                alert,
                ("role", "alertname", "namespace", "delay", "duration"),
                ("labels", "observation_delay_seconds"),
                file,
                af,
            )
            role = identifier(alert["role"], file, f"{af}.role")
            if role in roles:
                fail(
                    file,
                    f"{af}.role",
                    "duplicate role in this incident; give each explicit flapping occurrence a distinct role",
                )
            roles.add(role)
            text(alert["alertname"], file, f"{af}.alertname")
            text(alert["namespace"], file, f"{af}.namespace")
            explicit = labels(alert.get("labels", {}), file, f"{af}.labels")
            effective = {
                "alertname": alert["alertname"],
                "namespace": alert["namespace"],
                **explicit,
            }
            for key in ("alertname", "namespace"):
                if key in explicit and explicit[key] != alert[key]:
                    fail(
                        file,
                        f"{af}.labels.{key}",
                        f"conflicts with explicitly configured {key}",
                    )
            for key in sorted(target.keys() & effective.keys()):
                if target[key] != effective[key]:
                    label_field = (
                        f"{af}.labels.{key}" if key in explicit else f"{af}.{key}"
                    )
                    fail(
                        file,
                        label_field,
                        f"must agree with {field}.target.{key}; omit the target constraint for intentionally changing resources",
                    )
            distribution(alert["delay"], file, f"{af}.delay")
            distribution(alert["duration"], file, f"{af}.duration", duration=True)
            integer(
                alert.get("observation_delay_seconds", 0),
                file,
                f"{af}.observation_delay_seconds",
            )
    warnings = []
    if len(incidents) == 1:
        warnings.append(f"{file}: incidents: only one incident")
    if all(len(incident["alerts"]) != 1 for incident in incidents):
        warnings.append(f"{file}: incidents: no singleton incidents")
    for parameter in ("delay", "duration"):
        values = [
            alert[parameter] for incident in incidents for alert in incident["alerts"]
        ]
        if (
            all(value["distribution"] == "fixed" for value in values)
            and len({value["seconds"] for value in values}) == 1
        ):
            warnings.append(
                f"{file}: incidents[].alerts[].{parameter}: no {parameter} variation"
            )
    return warnings


def load_scenario(path):
    scenario, raw = read_yaml(path)
    warnings = validate_scenario(scenario, str(path))
    return scenario, raw, warnings
