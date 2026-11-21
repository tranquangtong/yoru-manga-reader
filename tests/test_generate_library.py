import contextlib
import io
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import generate_library as generator
import r2_client


class ManifestTests(unittest.TestCase):
    def test_local_scan_matches_relative_paths_and_preserves_manifest_rules(self):
        paths = [
            "2020-now Truyện 2/Chap 10/1.jpg",
            "2020-now Truyện 2/chapter2.5/10.jpg",
            "2020-now Truyện 2/chapter2.5/2.WEBP",
            "2020-now Truyện 2/chapter2.5/readme.txt",
            "2020-now Truyện 2/chapter2.5/nested/1.jpg",
            "2020-now Truyện 2/Ảnh_bìa/10.png",
            "2020-now Truyện 2/Ảnh_bìa/2.PNG",
            "2020-now Truyện 2/Ảnh_bìa-/1.png",
            "2020-now Truyện 2/cover.jpg",
            "2020-now Truyện 2/bonus/1.gif",
            "2020-now Truyện 10/THUMB.avif",
            "2020-now Truyện 10/chap X/1.jpg",
            "2020-now Truyện 10/chap 3/readme.txt",
            "Fallback/chap 1/1.jpeg",
            "Ignored/chap 1/1.jpg",
            "No cover/random.jpg",
            "root.jpg",
        ]
        excluded = {"Ignored"}
        with tempfile.TemporaryDirectory() as directory:
            library = Path(directory)
            for path in paths:
                image = library / path
                image.parent.mkdir(parents=True, exist_ok=True)
                image.touch()
            (library / "2020-now Truyện 2/chap 1").mkdir()
            (library / "Empty").mkdir()
            local = generator.scan_library(excluded, library_dir=library)
            tree_paths = [path.relative_to(library).as_posix() for path in library.rglob("*") if path.is_file()]
            self.assertEqual(local, generator.build_manifest(reversed(tree_paths), excluded))

        self.assertEqual(local["libraryPath"], "../library")
        self.assertEqual(
            [series["id"] for series in local["series"]],
            ["2020-now Truyện 2", "2020-now Truyện 10", "Fallback"],
        )
        first, second, third = local["series"]
        self.assertEqual(first["displayTitle"], "Truyện 2")
        self.assertEqual(first["years"], "2020-now")
        self.assertEqual(first["cover"], "2020-now Truyện 2/Ảnh_bìa/2.PNG")
        self.assertEqual(first["pageCount"], 3)
        self.assertEqual(
            first["chapters"],
            [
                {
                    "id": "Chap 10",
                    "label": "Chap 10",
                    "number": 10.0,
                    "path": "2020-now Truyện 2/Chap 10",
                    "pages": ["2020-now Truyện 2/Chap 10/1.jpg"],
                },
                {
                    "id": "chapter2.5",
                    "label": "Chap 2.5",
                    "number": 2.5,
                    "path": "2020-now Truyện 2/chapter2.5",
                    "pages": [f"2020-now Truyện 2/chapter2.5/{name}" for name in ("2.WEBP", "10.jpg")],
                },
            ],
        )
        self.assertEqual(second["cover"], "2020-now Truyện 10/THUMB.avif")
        self.assertEqual(second["chapters"], [])
        self.assertEqual(third["cover"], "Fallback/chap 1/1.jpeg")

    def test_generator_defaults_to_r2_and_does_not_rewrite_unchanged_output(self):
        credentials = r2_client.Credentials("example", "bucket", "custom/prefix", "id", "secret")
        with (
            tempfile.TemporaryDirectory() as directory,
            contextlib.redirect_stdout(io.StringIO()),
            patch.object(sys, "argv", ["generate_library.py", "--exclude-series", "Ignored"]),
            patch.object(generator, "load_credentials", return_value=credentials),
            patch.object(generator, "list_object_keys", return_value=[
                "custom/prefix/",
                "custom/prefix/Truyện/chap 1/1.jpg",
                "custom/prefix/Ignored/chap 1/1.jpg",
            ]) as list_keys,
        ):
            output = Path(directory) / "library-data.js"
            with patch.object(generator, "OUTPUT_FILE", output):
                generator.main()
                original = output.read_text(encoding="utf-8")
                _, payload = generator.parse_manifest(original)
                self.assertIn("generatedAt", payload)
                self.assertEqual(payload["series"][0]["cover"], "Truyện/chap 1/1.jpg")
                self.assertEqual(len(payload["series"]), 1)
                with patch.object(Path, "write_text") as write:
                    generator.main()
                write.assert_not_called()
                self.assertEqual(output.read_text(encoding="utf-8"), original)
            list_keys.assert_called_with(credentials)

    def test_updater_generate_only_passes_source_and_skips_git(self):
        script = Path(generator.__file__).with_name("update-site.py")
        updater = runpy.run_path(str(script))
        for arguments, source in (([], "r2"), (["--source", "local"], "local")):
            with (
                patch.object(sys, "argv", [script.name, "--generate-only", *arguments]),
                patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0)) as run,
                patch("shutil.which") as which,
            ):
                self.assertEqual(updater["main"](), 0)
                run.assert_called_once_with(
                    [sys.executable, str(Path(generator.__file__)), "--source", source],
                    cwd=generator.UI_DIR, check=False, text=True,
                )
                which.assert_not_called()
