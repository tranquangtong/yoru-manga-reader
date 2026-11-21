#!/usr/bin/env python3
"""Remove series whose cover returns HTTP 404 from the hosted manifest."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from generate_library import OUTPUT_FILE, UI_DIR, parse_manifest, serialize_manifest


CONFIG_FILE = UI_DIR / "config.js"
ASSET_BASE_RE = re.compile(
    r"""^\s*assetBaseUrl\s*:\s*(["'])([^\r\n]+?)\1""", re.MULTILINE
)


class CoverRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A redirect doesn't establish whether the original object is missing.
        return None


COVER_OPENER = build_opener(CoverRedirectHandler())


def read_asset_base(config_path: Path) -> str:
    match = ASSET_BASE_RE.search(config_path.read_text(encoding="utf-8"))
    if match:
        base = match.group(2)
        url = urlsplit(base)
        if url.scheme in {"http", "https"} and url.netloc and not (url.query or url.fragment):
            return base.removesuffix("/") + "/"
    raise ValueError("Không tìm thấy assetBaseUrl HTTP(S) hợp lệ trong config.js.")


def cover_url(base: str, path: str) -> str:
    # Match encodeURIComponent in app.js while retaining path separators.
    return base + quote(path, safe="/!'()*")


def check_cover(url: str) -> tuple[bool | None, str]:
    request = Request(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Range": "bytes=0-0"},
        method="GET",
    )
    try:
        with COVER_OPENER.open(request, timeout=10) as response:
            status = response.status
    except HTTPError as exc:
        exc.close()
        status = exc.code
    except (OSError, HTTPException, ValueError) as exc:
        return None, str(exc)

    if status in (200, 206):
        return True, ""
    if status == 404:
        return False, ""
    return None, f"HTTP {status}"


def prune_manifest(manifest_path: Path, config_path: Path, *, apply: bool) -> int:
    base = read_asset_base(config_path)
    header, payload = parse_manifest(manifest_path.read_text(encoding="utf-8"))
    kept = []
    missing = 0
    for series in payload["series"]:
        if not isinstance(series, dict) or not all(
            isinstance(series.get(field), str) and series[field]
            for field in ("id", "cover")
        ):
            raise ValueError("Bộ truyện trong library-data.js thiếu id hoặc đường dẫn ảnh bìa.")

        title = series["id"]
        present, detail = check_cover(cover_url(base, series["cover"]))
        if present is False:
            print(f"Thiếu ảnh bìa (HTTP 404): {title}")
            missing += 1
            continue
        if present is None:
            print(
                f"CẢNH BÁO: Giữ {title}. Không xác minh được ảnh bìa ({detail}).",
                file=sys.stderr,
            )
        kept.append(series)

    if apply and missing:
        payload["series"] = kept
        payload["generatedAt"] = datetime.now().astimezone().isoformat(timespec="seconds")
        manifest_path.write_text(serialize_manifest(payload, header), encoding="utf-8")
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Kiểm tra ảnh bìa của thư viện trên R2.")
    parser.add_argument(
        "--apply", action="store_true",
        help="Xóa khỏi manifest các bộ có ảnh bìa trả về 404.",
    )
    args = parser.parse_args()
    try:
        missing = prune_manifest(OUTPUT_FILE, CONFIG_FILE, apply=args.apply)
    except (OSError, ValueError) as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 1

    if not missing:
        print("Không phát hiện bộ truyện có ảnh bìa trả về 404.")
    elif args.apply:
        print(f"Đã xóa {missing} bộ truyện khỏi {OUTPUT_FILE.name}.")
    else:
        print(f"Tìm thấy {missing} bộ truyện thiếu ảnh bìa. Dùng --apply để cập nhật manifest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
