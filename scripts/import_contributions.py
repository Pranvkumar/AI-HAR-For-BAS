"""Import validated HAR contribution ZIP files into the local annotation queue."""

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def main() -> None:
    """Copy contributed source images into a class-organized annotation queue."""

    parser = argparse.ArgumentParser(description="Import a HAR image contribution ZIP.")
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/incoming_annotations"))
    args = parser.parse_args()
    if not zipfile.is_zipfile(args.archive):
        parser.error(f"Not a ZIP file: {args.archive}")
    with zipfile.ZipFile(args.archive) as contribution:
        try:
            manifest = json.loads(contribution.read("manifest.json"))
        except (KeyError, json.JSONDecodeError) as error:
            raise ValueError("Archive must contain a valid manifest.json.") from error
        if manifest.get("format") != "har-image-contribution-v1":
            raise ValueError("Unsupported contribution archive format.")
        class_name = str(manifest["class_name"])
        destination = args.output / class_name
        destination.mkdir(parents=True, exist_ok=True)
        imported = 0
        for info in contribution.infolist():
            filename = Path(info.filename).name
            if Path(filename).suffix.lower() not in IMAGE_SUFFIXES or "/" in info.filename.replace("\\", "/"):
                continue
            target = destination / filename
            with contribution.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
            imported += 1
    print(f"Imported {imported} unlabelled {class_name} images into {destination}.")
    print("Annotate their bounding boxes before moving them into data/tool_detection/images/.")


if __name__ == "__main__":
    main()
