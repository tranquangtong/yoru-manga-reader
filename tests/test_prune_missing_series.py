import contextlib
import io
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import generate_library as generator
import prune_missing_series as pruner


class PruneMissingSeriesTests(unittest.TestCase):
    def setUp(self):
        contexts = contextlib.ExitStack()
        self.addCleanup(contexts.close)
        directory = Path(contexts.enter_context(tempfile.TemporaryDirectory()))
        self.config = directory / "config.js"
        self.config.write_text(
            'window.YORU_CONFIG = Object.freeze({\n'
            '  // assetBaseUrl: "https://wrong.example/"\n'
            '  assetBaseUrl: "https://bucket.example/library",\n'
            '});\n',
            encoding="utf-8",
        )
        self.manifest = directory / "library-data.js"
        self.header = generator.MANIFEST_HEADER + "  "
        self.payload = {
            "generatedAt": "2000-01-01T00:00:00+00:00",
            "libraryPath": "../library",
            "series": [
                {"id": "Tập 1", "cover": "Tập 1/bìa !'()*.jpg", "chapters": []},
                {"id": "Thiếu", "cover": "Missing/cover.jpg", "chapters": []},
                {"id": "Chưa rõ", "cover": "Unknown/cover.jpg", "chapters": []},
            ],
        }
        self.manifest.write_text(
            generator.serialize_manifest(self.payload, self.header), encoding="utf-8"
        )
        self.stdout = contexts.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.stderr = contexts.enter_context(contextlib.redirect_stderr(io.StringIO()))
        contexts.enter_context(patch.object(pruner, "CONFIG_FILE", self.config))
        contexts.enter_context(patch.object(pruner, "OUTPUT_FILE", self.manifest))
        self.checker = contexts.enter_context(patch.object(
            pruner, "check_cover",
            side_effect=[(True, ""), (False, ""), (None, "HTTP 403")],
        ))

    def test_default_dry_run_reports_missing_and_retains_original_bytes(self):
        before = self.manifest.read_bytes()
        with patch.object(sys, "argv", ["prune_missing_series.py"]):
            self.assertEqual(pruner.main(), 0)

        self.assertEqual(self.manifest.read_bytes(), before)
        self.assertIn("Thiếu ảnh bìa (HTTP 404): Thiếu", self.stdout.getvalue())
        self.assertIn("Giữ Chưa rõ", self.stderr.getvalue())
        self.assertIn("HTTP 403", self.stderr.getvalue())
        self.assertEqual(self.checker.call_count, 3)
        self.assertEqual(
            self.checker.call_args_list[0].args,
            ("https://bucket.example/library/T%E1%BA%ADp%201/b%C3%ACa%20!'()*.jpg",),
        )

    def test_apply_preserves_header_and_round_trips_kept_series(self):
        with patch.object(sys, "argv", ["prune_missing_series.py", "--apply"]):
            self.assertEqual(pruner.main(), 0)

        written = self.manifest.read_text(encoding="utf-8")
        header, payload = generator.parse_manifest(written)
        self.assertEqual(header, self.header)
        self.assertEqual(payload["series"], self.payload["series"][::2])
        self.assertEqual(payload["libraryPath"], self.payload["libraryPath"])
        self.assertNotEqual(payload["generatedAt"], self.payload["generatedAt"])
        self.assertIsNotNone(datetime.fromisoformat(payload["generatedAt"]).tzinfo)
        self.assertEqual(written, generator.serialize_manifest(payload, self.header))
        self.assertIn('"id":"Tập 1","cover":"Tập 1/', written)


class CheckCoverTests(unittest.TestCase):
    def test_get_uses_range_and_user_agent_and_accepts_200_and_206(self):
        with patch.object(pruner.COVER_OPENER, "open") as open_url:
            response = open_url.return_value.__enter__.return_value
            for status in (200, 206):
                with self.subTest(status=status):
                    response.status = status
                    self.assertEqual(pruner.check_cover("https://bucket.example/cover.jpg"), (True, ""))
                    request = open_url.call_args.args[0]
                    self.assertEqual(request.get_method(), "GET")
                    self.assertEqual(request.get_header("User-agent"), "Mozilla/5.0")
                    self.assertEqual(request.get_header("Range"), "bytes=0-0")

    def test_only_404_is_confirmed_missing(self):
        url = "https://bucket.example/cover.jpg"
        statuses = [
            (404, (False, "")),
            (302, (None, "HTTP 302")),
            (403, (None, "HTTP 403")),
            (503, (None, "HTTP 503")),
        ]
        for status, expected in statuses:
            with self.subTest(status=status):
                error = HTTPError(url, status, "", {}, MagicMock())
                with patch.object(pruner.COVER_OPENER, "open", side_effect=error):
                    self.assertEqual(pruner.check_cover(url), expected)

        with patch.object(pruner.COVER_OPENER, "open", side_effect=URLError("offline")):
            present, detail = pruner.check_cover(url)
        self.assertIsNone(present)
        self.assertIn("offline", detail)


if __name__ == "__main__":
    unittest.main()
