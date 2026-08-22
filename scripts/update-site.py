#!/usr/bin/env python3
"""Regenerate the hosted library manifest and optionally publish it."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


UI_DIR = Path(__file__).resolve().parent.parent
GENERATOR = UI_DIR / "scripts" / "generate_library.py"


class UpdateError(RuntimeError):
    pass


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, cwd=UI_DIR, check=False, text=True)
    except OSError as exc:
        raise UpdateError(f"Không chạy được {command[0]}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cập nhật library-data.js từ library local và publish GitHub Pages."
    )
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="Chỉ tạo manifest, không commit hoặc push.",
    )
    args = parser.parse_args()

    try:
        generated = run([sys.executable, str(GENERATOR)])
        if generated.returncode != 0:
            raise UpdateError("Không tạo được library-data.js.")

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
    except UpdateError as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
