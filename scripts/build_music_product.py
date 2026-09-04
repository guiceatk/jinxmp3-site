#!/usr/bin/env python3
"""Build a validated, reversible digital-music product bundle.

The command never modifies or deletes the source audio.  It writes all derived
files to a product staging directory and emits a manifest consumed by the
Shopify sync agent.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_DIR / "staging" / "products"
LICENSE_TEXT = """COMMERCIAL LICENSE

This license is included with the digital release. The purchaser may use the
included audio in commercial projects according to the seller's terms.
Resale or redistribution of the source files as a standalone product is not
permitted.
"""


def slugify(value: str) -> str:
    value = re.sub(r"[^\w\s-]", "", value.lower()).strip()
    return re.sub(r"[\s_-]+", "-", value)


def find_source(track_id: str, explicit: str | None) -> Path:
    if explicit:
        source = Path(explicit).expanduser()
        if not source.is_file():
            raise FileNotFoundError(f"Audio source not found: {source}")
        return source

    candidates = [
        REPO_DIR / "public" / "releases" / track_id / "audio.mp3",
        REPO_DIR / "public" / "releases" / track_id / "audio.wav",
        Path.home() / "Music" / "Suno_DistroKid_Releases" / track_id,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
        if candidate.is_dir():
            audio = next((p for p in candidate.iterdir()
                          if p.suffix.lower() in {".mp3", ".wav", ".flac"}), None)
            if audio:
                return audio
    raise FileNotFoundError(
        f"No audio found for {track_id}; pass --source with an audio file"
    )


def find_cover(track_id: str, explicit: str | None) -> Path:
    candidates = [Path(explicit).expanduser()] if explicit else [
        REPO_DIR / "public" / "releases" / track_id / "cover.jpg",
        REPO_DIR / "public" / "releases" / track_id / "cover.jpeg",
        REPO_DIR / "public" / "releases" / track_id / "cover.png",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"No cover artwork found for {track_id}; pass --cover with an image file"
    )


def run_ffprobe(path: Path) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "json", str(path)],
            check=True, capture_output=True, text=True,
        )
        duration = float(json.loads(result.stdout)["format"]["duration"])
    except (OSError, subprocess.CalledProcessError, KeyError, ValueError,
            json.JSONDecodeError) as exc:
        raise RuntimeError("ffprobe is required to validate the audio source") from exc
    if duration <= 0:
        raise ValueError("Audio duration must be greater than zero")
    return duration


def make_preview(source: Path, destination: Path, seconds: int) -> None:
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(source), "-t", str(seconds),
             "-c", "copy", str(destination)],
            check=True, capture_output=True, text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("ffmpeg is required to render the audio preview") from exc


def build_product(args: argparse.Namespace) -> Path:
    source = find_source(args.track_id, args.source)
    cover = find_cover(args.track_id, args.cover)
    duration = run_ffprobe(source)
    title = args.title or source.stem
    slug = slugify(args.track_id or title)
    product_dir = Path(args.output_dir).expanduser() / slug
    product_dir.mkdir(parents=True, exist_ok=True)

    master = product_dir / f"{slug}{source.suffix.lower()}"
    shutil.copy2(source, master)
    cover_copy = product_dir / f"cover{cover.suffix.lower()}"
    shutil.copy2(cover, cover_copy)
    preview = product_dir / f"{slug}-preview{source.suffix.lower()}"
    make_preview(source, preview, min(args.preview_seconds, max(1, int(duration))))

    metadata = {
        "id": slug,
        "trackId": args.track_id,
        "title": title,
        "artist": args.artist,
        "producer": args.producer,
        "price": f"{args.price:.2f}",
        "durationSeconds": duration,
        "master": master.name,
        "preview": preview.name,
        "cover": cover_copy.name,
        "license": "COMMERCIAL_LICENSE.txt",
        "verified": True,
    }
    metadata_path = product_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    (product_dir / "COMMERCIAL_LICENSE.txt").write_text(LICENSE_TEXT, encoding="utf-8")

    manifest = product_dir / "product.json"
    manifest.write_text(json.dumps({
        "slug": slug,
        "title": title,
        "artist": args.artist,
        "producer": args.producer,
        "price": metadata["price"],
        "bundle": str(product_dir),
        "metadata": str(metadata_path),
        "verified": True,
    }, indent=2) + "\n", encoding="utf-8")

    zip_path = product_dir / f"{slug}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in (master, preview, cover_copy, metadata_path,
                     product_dir / "COMMERCIAL_LICENSE.txt"):
            bundle.write(path, path.name)
    print(f"[+] Product packaged: {zip_path}")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("track_id", help="Catalog track ID or product slug")
    parser.add_argument("--source", help="Path to the master audio file")
    parser.add_argument("--cover", help="Path to companion cover artwork")
    parser.add_argument("--title")
    parser.add_argument("--artist", default="jinx3")
    parser.add_argument("--producer", default="Guice Atkinson")
    parser.add_argument("--price", type=float, default=4.99)
    parser.add_argument("--preview-seconds", type=int, default=45)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    if args.preview_seconds < 1 or args.price < 0:
        parser.error("--preview-seconds must be positive and --price cannot be negative")
    try:
        build_product(args)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
