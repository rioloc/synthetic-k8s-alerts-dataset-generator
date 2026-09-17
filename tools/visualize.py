"""Render a canonical dataset as a PNG: python -m tools.visualize."""

import argparse
import os
from pathlib import Path
import sys
import tempfile
from textwrap import shorten

from generator.schema import ValidationError, fail, read_yaml
from generator.validate import UNRESOLVED, validate_dataset

# ponytail: one readable PNG, capped at 200 rows; add pagination for larger datasets.
MAX_EPISODES = 200


def create_figure(episodes, annotations, dataset_id):
    """Build an Agg figure from validated records, without a GUI or pyplot state."""
    if len(episodes) > MAX_EPISODES:
        fail(
            "episodes.yaml",
            "episodes",
            f"PNG visualization supports at most {MAX_EPISODES} episodes; use a smaller dataset",
        )
    try:
        import matplotlib as mpl
        from matplotlib.artist import Artist
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
        from matplotlib.lines import Line2D
        from matplotlib.patches import Patch
        from matplotlib.ticker import MaxNLocator
    except ImportError as exc:
        raise ValidationError(
            "visualization: matplotlib: optional plotting dependency is unavailable; install the project's visualization extra"
        ) from exc

    assignments = {
        item["episode_id"]: item["reference_incident_id"] for item in annotations
    }
    references = sorted(set(assignments.values()))
    palette = mpl.colormaps[
        "tab10"
        if len(references) <= 10
        else "tab20"
        if len(references) <= 20
        else "hsv"
    ]
    colors = {
        reference: "#777777"
        if reference in UNRESOLVED
        else palette(index if len(references) <= 20 else index / len(references))
        for index, reference in enumerate(references)
    }
    ordered = sorted(
        episodes, key=lambda episode: (episode["start"], episode["episode_id"])
    )
    # Ignore user plotting styles, including TeX settings that could run external tools.
    with mpl.rc_context({**mpl.rcParamsDefault, "text.parse_math": False}):
        figure = Figure(
            figsize=(15, max(3.5, len(ordered) * 0.55 + 1.8)), layout="constrained"
        )
        FigureCanvasAgg(figure)
        axis = figure.subplots()
        row_labels = []
        for row, episode in enumerate(ordered):
            reference = assignments[episode["episode_id"]]
            axis.barh(
                row,
                episode["end"] - episode["start"],
                left=episode["start"],
                height=0.55,
                color=colors[reference],
            )
            if "observed_at" in episode:
                axis.scatter(
                    episode["observed_at"],
                    row,
                    marker="D",
                    color="black",
                    s=24,
                    zorder=3,
                )
            labels = episode["labels"]
            resources = ", ".join(
                f"{key}={value}"
                for key, value in sorted(labels.items())
                if key not in ("alertname", "severity")
            )
            row_labels.append(
                f"{episode['episode_id']} | {shorten(labels['alertname'], width=42, placeholder='…')}\n"
                f"{shorten(reference, width=36, placeholder='…')} | {shorten(resources, width=65, placeholder='…')}"
            )
        axis.set_yticks(range(len(ordered)), row_labels, fontsize=8)
        axis.invert_yaxis()
        axis.set_xlabel("Seconds (relative time)")
        axis.xaxis.set_major_locator(MaxNLocator(integer=True))
        axis.ticklabel_format(axis="x", style="plain", useOffset=False)
        axis.set_axisbelow(True)
        axis.grid(axis="x", alpha=0.25)
        axis.margins(x=0.05)
        axis.set_title(
            f"{dataset_id}\nReference timeline — evaluator annotations, not algorithm predictions",
            fontsize=11,
        )
        handles: list[Artist] = [
            Patch(
                facecolor=colors[reference],
                label=f"{reference} (unresolved)"
                if reference in UNRESOLVED
                else reference,
            )
            for reference in references
        ]
        if any("observed_at" in episode for episode in ordered):
            handles.append(
                Line2D(
                    [],
                    [],
                    color="black",
                    marker="D",
                    linestyle="none",
                    markersize=5,
                    label="observed_at",
                )
            )
        axis.legend(
            handles=handles,
            title="Reference incident",
            loc="upper left",
            bbox_to_anchor=(1.01, 1),
            fontsize=8,
        )
    return figure


def save_png(figure, output):
    """Publish a fully rendered file with an exclusive, same-filesystem hard link."""
    output = Path(output)
    if output.suffix.lower() != ".png":
        fail(output, "$", "output filename must end in .png")
    if os.path.lexists(output):
        fail(output, "$", "output already exists; choose a new PNG path")
    # A private sibling is removed on success or failure; linking cannot overwrite
    # another writer's file, and readers only see the complete PNG.
    with tempfile.NamedTemporaryFile(
        dir=output.parent, prefix=".visualize-", suffix=".png"
    ) as temporary:
        figure.savefig(temporary, format="png", dpi=120)
        temporary.flush()
        os.fsync(temporary.fileno())
        os.link(temporary.name, output)


def visualize(dataset, output):
    dataset = Path(dataset)
    warnings = validate_dataset(dataset)
    episodes, _ = read_yaml(dataset / "episodes.yaml")
    annotations, _ = read_yaml(dataset / "annotations.yaml")
    manifest, _ = read_yaml(dataset / "manifest.yaml")
    figure = create_figure(
        episodes["episodes"], annotations["annotations"], manifest["dataset_id"]
    )
    try:
        save_png(figure, output)
    finally:
        figure.clear()
    return warnings


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Plot a validated dataset's episode intervals and reference assignments as a PNG"
    )
    parser.add_argument(
        "--dataset",
        required=True,
        help="directory containing the four canonical dataset files",
    )
    parser.add_argument(
        "--output", required=True, help="new .png file; its parent directory must exist"
    )
    args = parser.parse_args(argv)
    try:
        warnings = visualize(args.dataset, args.output)
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)
        print(f"Created {args.output}")
        return 0
    except (ValidationError, OSError, ValueError) as exc:
        print(f"error: {args.output}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
