#!/usr/bin/env python3
"""Scan the sibling manga library and generate the hosted reader manifest."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path


UI_DIR = Path(__file__).resolve().parent.parent
LIBRARY_DIR = UI_DIR.parent / "library"
OUTPUT_FILE = UI_DIR / "library-data.js"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
YEAR_PREFIX_RE = re.compile(
    r"^(?P<years>\d{4}(?:-(?:\d{4}|now|present|nay))?)\s+(?P<title>.+)$",
    re.IGNORECASE,
)
CHAPTER_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
CHAPTER_FOLDER_RE = re.compile(r"^chap(?:ter)?\s*\d", re.IGNORECASE)
COVER_FOLDER_NAMES = {
    "anh bia",
    "bia",
    "cover",
    "covers",
    "thumb",
    "thumbnail",
    "thumbnails",
}


def natural_key(value: str) -> tuple[tuple[int, object], ...]:
    """Sort names such as chap 2 before chap 10."""
    parts: list[tuple[int, object]] = []
    for part in re.split(r"(\d+)", value.casefold()):
        if not part:
            continue
        parts.append((0, int(part)) if part.isdigit() else (1, part))
    return tuple(parts)


def library_path(path: Path) -> str:
    return path.relative_to(LIBRARY_DIR).as_posix()


def normalized_folder_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    words = re.sub(r"[-_]+", " ", without_accents.casefold())
    return " ".join(words.split())


def images_in(directory: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.casefold() in IMAGE_SUFFIXES
        ),
        key=lambda path: natural_key(path.name),
    )


def chapter_label(folder_name: str) -> str:
    return re.sub(r"^chap(?:ter)?\s*", "Chap ", folder_name, flags=re.IGNORECASE)


def scan_library(excluded_series: set[str] | None = None) -> dict[str, object]:
    if not LIBRARY_DIR.is_dir():
        raise SystemExit(f"Không tìm thấy thư mục library: {LIBRARY_DIR}")

    excluded_series = excluded_series or set()
    series_items: list[dict[str, object]] = []
    series_directories = sorted(
        (
            path
            for path in LIBRARY_DIR.iterdir()
            if path.is_dir() and path.name not in excluded_series
        ),
        key=lambda path: natural_key(path.name),
    )

    for series_directory in series_directories:
        chapters: list[dict[str, object]] = []
        chapter_directories = sorted(
            (
                path
                for path in series_directory.iterdir()
                if path.is_dir() and CHAPTER_FOLDER_RE.match(path.name)
            ),
            key=lambda path: natural_key(path.name),
        )
        for chapter_directory in chapter_directories:
            pages = images_in(chapter_directory)
            if not pages:
                continue
            number_match = CHAPTER_NUMBER_RE.search(chapter_directory.name)
            chapters.append(
                {
                    "id": chapter_directory.name,
                    "label": chapter_label(chapter_directory.name),
                    "number": float(number_match.group()) if number_match else None,
                    "path": library_path(chapter_directory),
                    "pages": [library_path(page) for page in pages],
                }
            )

        cover_directories = sorted(
            (
                path
                for path in series_directory.iterdir()
                if path.is_dir()
                and normalized_folder_name(path.name) in COVER_FOLDER_NAMES
            ),
            key=lambda path: natural_key(path.name),
        )
        folder_covers: list[Path] = []
        for cover_directory in cover_directories:
            folder_covers.extend(images_in(cover_directory))

        explicit_covers = sorted(
            (
                path
                for path in series_directory.iterdir()
                if path.is_file()
                and path.stem.casefold() in {"cover", "thumbnail", "thumb"}
                and path.suffix.casefold() in IMAGE_SUFFIXES
            ),
            key=lambda path: natural_key(path.name),
        )
        cover = (
            library_path(folder_covers[0])
            if folder_covers
            else (
                library_path(explicit_covers[0])
                if explicit_covers
                else (chapters[0]["pages"][0] if chapters else None)
            )
        )
        if not cover:
            continue

        name_match = YEAR_PREFIX_RE.match(series_directory.name)
        display_title = (
            name_match.group("title") if name_match else series_directory.name
        )
        years = name_match.group("years") if name_match else ""
        page_count = sum(len(chapter["pages"]) for chapter in chapters)
        series_items.append(
            {
                "id": series_directory.name,
                "title": series_directory.name,
                "displayTitle": display_title,
                "years": years,
                "path": library_path(series_directory),
                "cover": cover,
                "pageCount": page_count,
                "chapters": chapters,
            }
        )

    return {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "libraryPath": "../library",
        "series": series_items,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the hosted manga manifest.")
    parser.add_argument(
        "--exclude-series",
        action="append",
        default=[],
        help="Tên folder bộ truyện cần tạm ẩn; có thể dùng nhiều lần.",
    )
    args = parser.parse_args()
    payload = scan_library(set(args.exclude_series))
    if OUTPUT_FILE.is_file():
        existing_text = OUTPUT_FILE.read_text(encoding="utf-8")
        prefix = "window.MANGA_LIBRARY = "
        start = existing_text.find(prefix)
        if start >= 0:
            raw_payload = existing_text[start + len(prefix):].strip().removesuffix(";")
            try:
                existing_payload = json.loads(raw_payload)
            except json.JSONDecodeError:
                existing_payload = None
            if (
                isinstance(existing_payload, dict)
                and existing_payload.get("libraryPath") == payload["libraryPath"]
                and existing_payload.get("series") == payload["series"]
            ):
                print(f"{OUTPUT_FILE.name} đã khớp với library; không cần cập nhật.")
                return

    javascript = (
        "// Generated by generate_library.py — do not edit by hand.\n"
        "window.MANGA_LIBRARY = "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
    )
    OUTPUT_FILE.write_text(javascript, encoding="utf-8")
    chapter_count = sum(len(series["chapters"]) for series in payload["series"])
    page_count = sum(series["pageCount"] for series in payload["series"])
    print(
        f"Đã cập nhật {OUTPUT_FILE.name}: {len(payload['series'])} bộ truyện, "
        f"{chapter_count} chapter, {page_count} trang."
    )


if __name__ == "__main__":
    main()
