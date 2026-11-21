#!/usr/bin/env python3
"""Regenerate the hosted library manifest and optionally publish it."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys

from generate_library import OUTPUT_FILE, UI_DIR, parse_manifest

GENERATOR = UI_DIR / "scripts" / "generate_library.py"
PRUNER = UI_DIR / "scripts" / "prune_missing_series.py"


class UpdateError(RuntimeError):
    pass


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, cwd=UI_DIR, check=False, text=True)
    except OSError as exc:
        raise UpdateError(f"Không chạy được {command[0]}: {exc}") from exc


def restore_if_unchanged(previous: bytes | None) -> None:
    if previous is None:
        return
    current = OUTPUT_FILE.read_bytes()
    if previous == current:
        return
    try:
        _, old_payload = parse_manifest(previous.decode("utf-8"))
    except ValueError:
        return
    _, new_payload = parse_manifest(current.decode("utf-8"))
    old_payload.pop("generatedAt", None)
    new_payload.pop("generatedAt", None)
    if old_payload == new_payload:
        OUTPUT_FILE.write_bytes(previous)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cập nhật library-data.js từ library local và publish GitHub Pages."
    )
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="Chỉ tạo manifest, không commit hoặc push.",
    )
    parser.add_argument(
        "--skip-r2-check",
        action="store_true",
        help="Tạo manifest từ library local mà không kiểm tra ảnh bìa trên R2.",
    )
    args = parser.parse_args()

    try:
        previous = None
        if not args.skip_r2_check and OUTPUT_FILE.is_file():
            previous = OUTPUT_FILE.read_bytes()
        generated = run([sys.executable, str(GENERATOR)])
        if generated.returncode != 0:
            raise UpdateError("Không tạo được library-data.js.")

        if not args.skip_r2_check:
            pruned = run([sys.executable, str(PRUNER), "--apply"])
            if pruned.returncode != 0:
                if previous is not None:
                    OUTPUT_FILE.write_bytes(previous)
                raise UpdateError("Không kiểm tra được ảnh bìa trên R2.")
            restore_if_unchanged(previous)

        git = shutil.which("git")
        if not git:
            raise UpdateError("Không tìm thấy Git trên máy.")
        changed = run([git, "diff", "--quiet", "--", "library-data.js"])
        if changed.returncode == 0:
            print("UI đã khớp với library; không cần commit.")
            return 0
        if changed.returncode != 1:
            raise UpdateError("Không kiểm tra được thay đổi của library-data.js.")
        if args.generate_only:
            print("Đã tạo manifest mới; chưa commit hoặc push.")
            return 0

        if run([git, "add", "--", "library-data.js"]).returncode != 0:
            raise UpdateError("Không stage được library-data.js.")
        if run([git, "commit", "-m", "Update manga library", "--", "library-data.js"]).returncode != 0:
            raise UpdateError("Không commit được library-data.js.")
        if run([git, "push", "origin", "main"]).returncode != 0:
            raise UpdateError("Đã commit nhưng push lên GitHub thất bại.")
        print("Đã cập nhật GitHub Pages.")
        return 0
    except (UpdateError, OSError, ValueError) as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
