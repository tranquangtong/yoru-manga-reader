import contextlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import r2_client as r2


class R2ListingTests(unittest.TestCase):
    credentials = r2.Credentials("exampleaccount", "yoru-manga", "library", "test-access", "test-secret")

    def test_sigv4_matches_precomputed_signature_and_encodes_query(self):
        request = r2.signed_request(
            self.credentials,
            {"list-type": "2", "prefix": "library/", "continuation-token": "a+b/= &é", "max-keys": "1000"},
            datetime(2024, 11, 21, 12, 34, 56, tzinfo=timezone.utc),
        )
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(
            request.full_url,
            "https://exampleaccount.r2.cloudflarestorage.com/yoru-manga"
            "?continuation-token=a%2Bb%2F%3D%20%26%C3%A9&list-type=2&max-keys=1000&prefix=library%2F",
        )
        self.assertEqual(
            request.get_header("Authorization"),
            "AWS4-HMAC-SHA256 Credential=test-access/20241121/auto/s3/aws4_request, "
            "SignedHeaders=host;x-amz-content-sha256;x-amz-date, "
            "Signature=fd0d6adbd0cbde8c7e753963aa5463b3c8ffd3ad0adcbcae943c8f0b8f586444",
        )

    def test_list_objects_paginates_with_opaque_token(self):
        first = b"""
            <ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
              <IsTruncated>true</IsTruncated>
              <Contents><Key>library/Series &amp; more/chap 1/1.jpg</Key></Contents>
              <NextContinuationToken>a+b/= &amp; x</NextContinuationToken>
            </ListBucketResult>
        """
        last = b"""
            <ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
              <IsTruncated>false</IsTruncated>
              <Contents><Key>library/Series &amp; more/chap 1/2.jpg</Key></Contents>
            </ListBucketResult>
        """
        with patch.object(r2, "urlopen", side_effect=[io.BytesIO(first), io.BytesIO(last)]) as open_url:
            self.assertEqual(r2.list_object_keys(self.credentials), [
                "library/Series & more/chap 1/1.jpg", "library/Series & more/chap 1/2.jpg",
            ])
        first_request, last_request = (call.args[0] for call in open_url.call_args_list)
        query = {"list-type": ["2"], "max-keys": ["1000"], "prefix": ["library/"]}
        self.assertEqual(parse_qs(urlsplit(first_request.full_url).query), query)
        self.assertEqual(parse_qs(urlsplit(last_request.full_url).query),
                         {**query, "continuation-token": ["a+b/= & x"]})

    def test_incomplete_pagination_fails_and_http_errors_hide_response_body(self):
        missing_token = b"<ListBucketResult><IsTruncated>true</IsTruncated></ListBucketResult>"
        with patch.object(r2, "urlopen", return_value=io.BytesIO(missing_token)):
            with self.assertRaisesRegex(r2.R2Error, "continuation token"):
                r2.list_object_keys(self.credentials)
        error = HTTPError("https://example.com", 403, "test-secret", {}, io.BytesIO(b"test-secret"))
        with patch.object(r2, "urlopen", side_effect=error):
            with self.assertRaises(r2.R2Error) as failure:
                r2.list_object_keys(self.credentials)
        self.assertIn("403", str(failure.exception))
        self.assertNotIn("test-secret", str(failure.exception))


class CredentialsTests(unittest.TestCase):
    def setUp(self):
        contexts = contextlib.ExitStack()
        self.addCleanup(contexts.close)
        directory = Path(contexts.enter_context(tempfile.TemporaryDirectory()))
        self.settings_path = directory / "Yoru Manga" / "r2-upload.json"
        contexts.enter_context(patch.object(r2, "SETTINGS_PATH", self.settings_path))
        contexts.enter_context(patch.dict(os.environ, {}, clear=True))
        self.stdout = contexts.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.stderr = contexts.enter_context(contextlib.redirect_stderr(io.StringIO()))

    def test_env_fields_override_settings_and_env_secret_skips_keychain(self):
        r2.write_settings(r2.Credentials("savedaccount", "saved-bucket", "saved-prefix", "saved-id", "unused"))
        os.environ.update(R2_ACCOUNT_ID=" envaccount ", R2_BUCKET="env-bucket",
                          R2_PREFIX="/env-prefix/", R2_ACCESS_KEY_ID="env-id",
                          R2_SECRET_ACCESS_KEY="env-secret")
        with (
            patch.object(r2, "keychain_secret") as lookup,
            patch.object(r2, "read_settings") as settings,
        ):
            credentials = r2.load_credentials()
        self.assertEqual(credentials, r2.Credentials("envaccount", "env-bucket", "env-prefix", "env-id", "env-secret"))
        lookup.assert_not_called()
        settings.assert_not_called()
        self.assertNotIn("env-secret", repr(credentials) + self.stdout.getvalue() + self.stderr.getvalue())

    def test_settings_supply_missing_fields_and_keychain_uses_selected_access_key(self):
        r2.write_settings(r2.Credentials("savedaccount", "saved-bucket", "saved-prefix", "saved-id", "unused"))
        os.environ.update(R2_ACCESS_KEY_ID="env-id")
        success = subprocess.CompletedProcess([], 0, stdout="keychain-secret\n", stderr="")
        with (
            patch.object(r2.sys, "platform", "darwin"),
            patch.object(r2.subprocess, "run", return_value=success) as run,
        ):
            credentials = r2.load_credentials()
        self.assertEqual(credentials, r2.Credentials("savedaccount", "saved-bucket", "saved-prefix", "env-id", "keychain-secret"))
        run.assert_called_once_with(
            ["/usr/bin/security", "find-generic-password", "-s", "Yoru Manga R2 uploader", "-a", "env-id", "-w"],
            capture_output=True, text=True, check=False,
        )
        self.assertNotIn("keychain-secret", self.stdout.getvalue() + self.stderr.getvalue())

    def test_missing_credentials_prompt_once_and_store_only_metadata_in_mac_settings(self):
        with (
            patch.object(r2.sys, "platform", "darwin"),
            patch("builtins.input", side_effect=["promptaccount", "prompt-id"]),
            patch.object(r2.getpass, "getpass", return_value="prompt-secret") as prompt,
            patch.object(r2, "keychain_secret", return_value=""),
            patch.object(r2, "save_keychain_secret") as save,
        ):
            credentials = r2.load_credentials()
        self.assertEqual(credentials, r2.Credentials("promptaccount", "yoru-manga", "library", "prompt-id", "prompt-secret"))
        prompt.assert_called_once()
        save.assert_called_once_with("prompt-id", "prompt-secret")
        stored = self.settings_path.read_text(encoding="utf-8")
        self.assertEqual(json.loads(stored), {
            "account_id": "promptaccount", "bucket": "yoru-manga", "prefix": "library", "access_key_id": "prompt-id",
        })
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(self.settings_path.stat().st_mode), 0o600)
        self.assertNotIn("prompt-secret", stored + self.stdout.getvalue() + self.stderr.getvalue())

    def test_non_mac_prompts_for_secret_without_persisting_it(self):
        os.environ.update(R2_ACCOUNT_ID="envaccount", R2_ACCESS_KEY_ID="env-id")
        with (
            patch.object(r2.sys, "platform", "win32"),
            patch.object(r2.getpass, "getpass", return_value="prompt-secret") as prompt,
            patch.object(r2, "keychain_secret") as lookup,
            patch.object(r2, "save_keychain_secret") as save,
        ):
            self.assertEqual(r2.load_credentials().secret_access_key, "prompt-secret")
            self.assertEqual(r2.load_credentials().secret_access_key, "prompt-secret")
        self.assertEqual(prompt.call_count, 2)
        lookup.assert_not_called()
        save.assert_not_called()
        self.assertFalse(self.settings_path.exists())
        self.assertNotIn("prompt-secret", self.stdout.getvalue() + self.stderr.getvalue())
