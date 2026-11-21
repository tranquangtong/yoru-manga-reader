"""List Cloudflare R2 object keys using the S3 API."""

from __future__ import annotations

import getpass
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import tempfile
import warnings
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


SETTINGS_PATH = Path.home() / "Library" / "Application Support" / "Yoru Manga" / "r2-upload.json"
KEYCHAIN_SERVICE = "Yoru Manga R2 uploader"
DEFAULT_BUCKET = "yoru-manga"
DEFAULT_PREFIX = "library"


class R2Error(RuntimeError):
    pass


@dataclass(frozen=True)
class Credentials:
    account_id: str
    bucket: str
    prefix: str
    access_key_id: str
    secret_access_key: str = field(repr=False)

    @property
    def object_prefix(self) -> str:
        return f"{self.prefix}/" if self.prefix else ""


def read_settings() -> dict[str, str]:
    try:
        settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        raise R2Error("Không đọc được cấu hình R2 đã lưu.") from None
    if not isinstance(settings, dict):
        raise R2Error("Cấu hình R2 đã lưu không hợp lệ.")
    return {key: value.strip() for key, value in settings.items() if isinstance(value, str)}


def write_settings(credentials: Credentials) -> None:
    settings = {
        "account_id": credentials.account_id,
        "bucket": credentials.bucket,
        "prefix": credentials.prefix,
        "access_key_id": credentials.access_key_id,
    }
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=SETTINGS_PATH.parent, delete=False
    ) as config_file:
        temporary_path = Path(config_file.name)
        try:
            temporary_path.chmod(0o600)
            config_file.write(json.dumps(settings, ensure_ascii=False, indent=2) + "\n")
            config_file.close()
            temporary_path.replace(SETTINGS_PATH)
        finally:
            temporary_path.unlink(missing_ok=True)


def keychain_secret(access_key_id: str) -> str:
    result = subprocess.run(
        ["/usr/bin/security", "find-generic-password", "-s", KEYCHAIN_SERVICE,
         "-a", access_key_id, "-w"],
        capture_output=True, text=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def save_keychain_secret(access_key_id: str, secret: str) -> None:
    result = subprocess.run(
        ["/usr/bin/security", "add-generic-password", "-U", "-s", KEYCHAIN_SERVICE,
         "-a", access_key_id, "-w", secret],
        capture_output=True, check=False,
    )
    if result.returncode != 0:
        raise R2Error("Không lưu được Secret Access Key vào macOS Keychain.")


def load_credentials() -> Credentials:
    account_id = os.environ.get("R2_ACCOUNT_ID", "").strip()
    bucket = os.environ.get("R2_BUCKET", "").strip()
    prefix = os.environ.get("R2_PREFIX", "").strip()
    access_key_id = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
    secret = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
    settings = {} if all((account_id, bucket, prefix, access_key_id, secret)) else read_settings()
    account_id = account_id or settings.get("account_id", "")
    bucket = bucket or settings.get("bucket") or DEFAULT_BUCKET
    prefix = (prefix or settings.get("prefix", DEFAULT_PREFIX)).strip("/")
    access_key_id = access_key_id or settings.get("access_key_id", "")
    on_mac = sys.platform == "darwin"
    prompted = not (account_id and access_key_id)

    try:
        account_id = account_id or input("Cloudflare Account ID: ").strip()
        access_key_id = access_key_id or input("R2 Access Key ID: ").strip()
        if not account_id or not access_key_id:
            raise R2Error("Thiếu Account ID hoặc Access Key.")
        if not secret and on_mac:
            secret = keychain_secret(access_key_id)
        if not secret:
            prompted = True
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                secret = getpass.getpass("R2 Secret Access Key (ký tự sẽ được ẩn): ").strip()
    except (EOFError, getpass.GetPassWarning):
        raise R2Error(
            "Mở terminal để nhập thông tin xác thực R2 hoặc đặt các biến môi trường R2."
        ) from None
    except OSError:
        raise R2Error("Không đọc được thông tin xác thực R2.") from None

    if not secret:
        raise R2Error("Thiếu Secret Access Key.")
    credentials = Credentials(account_id, bucket, prefix, access_key_id, secret)
    if on_mac and prompted:
        try:
            save_keychain_secret(access_key_id, secret)
            write_settings(credentials)
        except OSError:
            raise R2Error("Không lưu được cấu hình R2 trên macOS.") from None
    return credentials


def signed_request(
    credentials: Credentials, query: dict[str, str], now: datetime
) -> Request:
    if not re.fullmatch(r"[a-zA-Z0-9]+", credentials.account_id):
        raise R2Error("Cloudflare Account ID không hợp lệ.")
    host = f"{credentials.account_id}.r2.cloudflarestorage.com"
    path = "/" + quote(credentials.bucket, safe="-_.~")
    encoded_query = sorted(
        (quote(key, safe="-_.~"), quote(value, safe="-_.~")) for key, value in query.items()
    )
    canonical_query = "&".join(f"{key}={value}" for key, value in encoded_query)
    now = now.astimezone(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(b"").hexdigest()
    headers = {
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
    }
    signed_headers = ";".join(headers)
    canonical_headers = "".join(f"{name}:{value}\n" for name, value in headers.items())
    canonical_request = "\n".join(
        ("GET", path, canonical_query, canonical_headers, signed_headers, payload_hash)
    )
    scope = f"{date_stamp}/auto/s3/aws4_request"
    string_to_sign = "\n".join(
        ("AWS4-HMAC-SHA256", amz_date, scope,
         hashlib.sha256(canonical_request.encode()).hexdigest())
    )
    key = ("AWS4" + credentials.secret_access_key).encode()
    for part in scope.split("/"):
        key = hmac.digest(key, part.encode(), "sha256")
    signature = hmac.new(key, string_to_sign.encode(), "sha256").hexdigest()
    headers["authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={credentials.access_key_id}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return Request(f"https://{host}{path}?{canonical_query}", headers=headers)


def list_object_keys(credentials: Credentials) -> list[str]:
    prefix = credentials.object_prefix
    query = {"list-type": "2", "max-keys": "1000", "prefix": prefix}
    keys: list[str] = []
    seen_tokens: set[str] = set()
    while True:
        request = signed_request(credentials, query, datetime.now(timezone.utc))
        try:
            with urlopen(request, timeout=60) as response:
                root = ET.fromstring(response.read())
        except HTTPError as exc:
            exc.close()
            raise R2Error(f"Không liệt kê được object trên R2 (HTTP {exc.code}).") from None
        except OSError:
            raise R2Error("Không kết nối được R2.") from None
        except ET.ParseError:
            raise R2Error("R2 trả về danh sách object không hợp lệ.") from None

        truncated = root.findtext("{*}IsTruncated")
        if root.tag.rsplit("}", 1)[-1] != "ListBucketResult" or truncated not in {"true", "false"}:
            raise R2Error("R2 trả về danh sách object không hợp lệ.")
        for item in root.findall("{*}Contents"):
            key = item.findtext("{*}Key")
            if not key or not key.startswith(prefix):
                raise R2Error("R2 trả về đường dẫn object không hợp lệ.")
            keys.append(key)
        if truncated == "false":
            return keys
        token = root.findtext("{*}NextContinuationToken")
        if not token or token in seen_tokens:
            raise R2Error("R2 thiếu continuation token mới cho trang kế tiếp.")
        seen_tokens.add(token)
        query["continuation-token"] = token
