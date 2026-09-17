import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from generator.generate import materialize
from generator.output import build_artifacts, publish
from generator.schema import ValidationError, load_scenario
from tools.visualize import MAX_EPISODES, create_figure, main, save_png, visualize

ROOT = Path(__file__).resolve().parents[1]
HAS_MATPLOTLIB = importlib.util.find_spec("matplotlib") is not None


def records(number):
    path = next((ROOT / "examples").glob(f"{number:02d}-*/scenario.yaml"))
    scenario, raw, _ = load_scenario(path)
    episodes, annotations = materialize(scenario, 424242)
    return scenario, raw, episodes["episodes"], annotations["annotations"]


def dataset(base, number):
    scenario, raw, _, _ = records(number)
    output = base / f"dataset-{number}"
    artifacts, _ = build_artifacts(scenario, 424242, raw)
    publish(artifacts, output)
    return output


class VisualizerBoundaryTests(unittest.TestCase):
    def test_help_does_not_require_plotting_imports(self):
        with (
            patch.dict(sys.modules, {"matplotlib": None}),
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            with self.assertRaises(SystemExit) as exit_context:
                main(["--help"])
        self.assertEqual(exit_context.exception.code, 0)
        self.assertIn("--dataset", output.getvalue())

    def test_missing_optional_dependency_is_actionable(self):
        _, _, episodes, annotations = records(1)
        with patch.dict(sys.modules, {"matplotlib": None}):
            with self.assertRaisesRegex(
                ValidationError, "optional plotting dependency.*visualization extra"
            ):
                create_figure(episodes, annotations, "fixture")

    def test_large_dataset_fails_before_rendering(self):
        _, _, episodes, annotations = records(1)
        oversized = [episodes[0]] * (MAX_EPISODES + 1)
        with self.assertRaisesRegex(ValidationError, "at most 200 episodes"):
            create_figure(oversized, annotations, "fixture")

    def test_invalid_dataset_returns_nonzero_without_png(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            output = dataset(base, 1)
            (output / "annotations.yaml").write_text("annotations: []\n")
            image = base / "invalid.png"
            with contextlib.redirect_stderr(io.StringIO()) as error:
                result = main(["--dataset", str(output), "--output", str(image)])
            self.assertEqual(result, 1)
            self.assertIn("annotations.yaml: annotations:", error.getvalue())
            self.assertFalse(image.exists())


@unittest.skipUnless(
    HAS_MATPLOTLIB, "optional Matplotlib visualization dependency is not installed"
)
class VisualizerTests(unittest.TestCase):
    def test_interval_lengths_labels_and_observation_coordinates(self):
        _, _, episodes, annotations = records(1)
        figure = create_figure(episodes, annotations, "fixture")
        self.addCleanup(figure.clear)
        axis = figure.axes[0]
        self.assertEqual(
            [(bar.get_x(), bar.get_width()) for bar in axis.patches],
            [(100, 120), (120, 70), (145, 90)],
        )
        self.assertEqual(
            [marker.get_offsets().tolist() for marker in axis.collections],
            [[[105, 0]], [[130, 1]], [[147, 2]]],
        )
        labels = "\n".join(label.get_text() for label in axis.get_yticklabels())
        for value in (
            "e-000001",
            "KubeNodeNotReady",
            "node=node-a",
            "instance=node-a",
            "namespace=openshift-monitoring",
            "incident-node-a",
        ):
            self.assertIn(value, labels)
        self.assertIn("not algorithm predictions", axis.get_title())
        self.assertEqual(axis.get_xlabel(), "Seconds (relative time)")

    def test_observation_after_end_is_visible_on_its_own_row(self):
        _, _, episodes, annotations = records(6)
        figure = create_figure(episodes, annotations, "fixture")
        self.addCleanup(figure.clear)
        axis = figure.axes[0]
        self.assertEqual(axis.collections[0].get_offsets().tolist(), [[180, 0]])
        self.assertEqual(axis.collections[1].get_offsets().tolist(), [[115, 1]])
        self.assertGreater(axis.get_xlim()[1], 180)
        first = axis.patches[0]
        self.assertEqual(first.get_x() + first.get_width(), 120)

    def test_flapping_retains_gaps_and_shared_reference_color(self):
        _, _, episodes, annotations = records(3)
        figure = create_figure(episodes, annotations, "fixture")
        self.addCleanup(figure.clear)
        bars = figure.axes[0].patches
        self.assertEqual((bars[0].get_x(), bars[0].get_width()), (100, 30))
        self.assertEqual((bars[1].get_x(), bars[1].get_width()), (170, 25))
        self.assertEqual(bars[0].get_facecolor(), bars[1].get_facecolor())
        self.assertEqual(bars[0].get_facecolor(), bars[3].get_facecolor())
        self.assertNotEqual(bars[0].get_facecolor(), bars[2].get_facecolor())

    def test_independent_overlaps_keep_distinct_colors_and_legend(self):
        _, _, episodes, annotations = records(2)
        figure = create_figure(episodes, annotations, "fixture")
        self.addCleanup(figure.clear)
        axis = figure.axes[0]
        bars = axis.patches
        self.assertEqual(bars[0].get_facecolor(), bars[2].get_facecolor())
        self.assertEqual(bars[1].get_facecolor(), bars[3].get_facecolor())
        self.assertNotEqual(bars[0].get_facecolor(), bars[1].get_facecolor())
        self.assertEqual(
            [label.get_text() for label in axis.get_legend().get_texts()],
            ["incident-node-a", "incident-node-b", "observed_at"],
        )

    def test_historical_data_does_not_invent_observation_markers(self):
        _, _, episodes, annotations = records(1)
        for episode in episodes:
            del episode["observed_at"]
        figure = create_figure(episodes, annotations, "fixture")
        self.addCleanup(figure.clear)
        axis = figure.axes[0]
        self.assertEqual(len(axis.collections), 0)
        self.assertNotIn(
            "observed_at", [label.get_text() for label in axis.get_legend().get_texts()]
        )

    def test_labels_are_literal_not_tex_or_math(self):
        import matplotlib as mpl

        _, _, episodes, annotations = records(1)
        episodes[0]["labels"]["alertname"] = r"$\notacommand$"
        with mpl.rc_context({"text.usetex": True, "text.parse_math": True}):
            figure = create_figure(episodes, annotations, "fixture")
        self.addCleanup(figure.clear)
        for label in figure.axes[0].get_yticklabels():
            self.assertFalse(label.get_usetex())
            self.assertFalse(label.get_parse_math())
        figure.canvas.draw()

    def test_all_examples_render_decodable_png_without_changing_dataset(self):
        from PIL import Image

        examples = sorted((ROOT / "examples").glob("*/scenario.yaml"))
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for path in examples:
                number = int(path.parent.name.split("-", 1)[0])
                with self.subTest(example=number):
                    source = dataset(base, number)
                    before = {path.name: path.read_bytes() for path in source.iterdir()}
                    output = base / f"timeline-{number}.png"
                    visualize(source, output)
                    self.assertEqual(output.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
                    # Pillow is already a Matplotlib dependency; decode at native
                    # 8-bit depth instead of allocating a float array for 200 rows.
                    with Image.open(output) as image:
                        self.assertEqual(image.format, "PNG")
                        self.assertGreater(image.height, 300)
                        self.assertGreater(image.width, 1000)
                        extrema = image.convert("RGB").getextrema()
                        self.assertTrue(any(low < high for low, high in extrema))
                    self.assertEqual(
                        before,
                        {path.name: path.read_bytes() for path in source.iterdir()},
                    )
            self.assertEqual(len(list(base.iterdir())), 2 * len(examples))

    def test_existing_png_and_invalid_extensions_are_refused(self):
        _, _, episodes, annotations = records(1)
        figure = create_figure(episodes, annotations, "fixture")
        self.addCleanup(figure.clear)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "existing.png"
            output.write_bytes(b"user image")
            with self.assertRaisesRegex(ValidationError, "output already exists"):
                save_png(figure, output)
            self.assertEqual(output.read_bytes(), b"user image")
            invalid = Path(temporary) / "not-png.svg"
            with self.assertRaisesRegex(ValidationError, "must end in .png"):
                save_png(figure, invalid)
            self.assertFalse(invalid.exists())

    def test_failed_render_or_publication_leaves_no_partial_image(self):
        _, _, episodes, annotations = records(1)
        figure = create_figure(episodes, annotations, "fixture")
        self.addCleanup(figure.clear)
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for target in (
                "tools.visualize.os.link",
                "matplotlib.figure.Figure.savefig",
            ):
                with (
                    self.subTest(target=target),
                    patch(target, side_effect=OSError("injected failure")),
                ):
                    with self.assertRaisesRegex(OSError, "injected failure"):
                        save_png(figure, base / "failed.png")
                    self.assertEqual(list(base.iterdir()), [])

    def test_competing_output_is_preserved_at_publication(self):
        _, _, episodes, annotations = records(1)
        figure = create_figure(episodes, annotations, "fixture")
        self.addCleanup(figure.clear)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "race.png"

            def competing_writer(source, destination):
                Path(destination).write_bytes(b"other writer")
                raise FileExistsError("output appeared during rendering")

            with patch("tools.visualize.os.link", side_effect=competing_writer):
                with self.assertRaises(FileExistsError):
                    save_png(figure, output)
            self.assertEqual(output.read_bytes(), b"other writer")
            self.assertEqual(list(Path(temporary).iterdir()), [output])

    def test_cli_and_make_target_accept_paths_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix="visualize tests ") as temporary:
            base = Path(temporary)
            source = dataset(base, 6)
            for command, output in (
                (
                    [
                        sys.executable,
                        "-m",
                        "tools.visualize",
                        "--dataset",
                        str(source),
                        "--output",
                        str(base / "CLI timeline.png"),
                    ],
                    base / "CLI timeline.png",
                ),
                (
                    [
                        "make",
                        "visualize",
                        f"PYTHON={sys.executable}",
                        f"OUTPUT={source}",
                        f"PNG={base / 'Make timeline.png'}",
                    ],
                    base / "Make timeline.png",
                ),
            ):
                result = subprocess.run(
                    command, cwd=ROOT, capture_output=True, text=True, timeout=30
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(output.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    unittest.main()
