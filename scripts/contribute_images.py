"""Package a friend's local HAR reference photos into one shareable ZIP file."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

OBJECT_CLASSES = (
    "outer_container",
    "red_box",
    "second_colored_box",
    "astronaut_hand",
)
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def main() -> None:
    """Validate local image files and create a portable contribution archive."""

    parser = argparse.ArgumentParser(description="Package photos for the offline HAR dataset.")
    parser.add_argument("--class-name", choices=OBJECT_CLASSES, required=True)
    parser.add_argument("--input", type=Path, required=True, help="Folder containing only the contributed photos")
    parser.add_argument("--contributor", required=True, help="First name or non-sensitive nickname")
    parser.add_argument("--output", type=Path, default=Path("har-contribution.zip"))
    args = parser.parse_args()
    if not args.input.is_dir():
        parser.error(f"Input folder does not exist: {args.input}")
    images = sorted(path for path in args.input.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)
    if not images:
        parser.error("No .jpg, .jpeg, .png, or .webp images were found.")
    created_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "format": "har-image-contribution-v1",
        "class_name": args.class_name,
        "contributor": args.contributor,
        "created_at": created_at,
        "image_count": len(images),
        "license_confirmation": "Contributor confirms they created these images or have permission to share them for this project.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        staging = Path(temporary)
        for index, image in enumerate(images, start=1):
            destination = staging / f"{args.class_name}_{index:04d}{image.suffix.lower()}"
            shutil.copy2(image, destination)
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as archive:
            for item in staging.iterdir():
                archive.write(item, item.name)
    print(f"Created {args.output} with {len(images)} images. Send this ZIP file to the project owner.")


if __name__ == "__main__":
    main()
