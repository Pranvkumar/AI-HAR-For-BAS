"""Download optional public datasets for AEGIS pretraining.

The final SIH object labels are never downloaded from the internet. Put reviewed
private labels under ``datasets/objects`` after downloading them separately.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "datasets" / "public"
KAGGLE_CACHE = Path.home() / ".cache" / "kagglehub"

DATASETS = {
    "hagrid": {
        "group": "hand",
        "license": "CC BY-SA 4.0",
        "url": "https://github.com/hukenovs/hagrid",
        "note": "Use Kaggle or the official downloader for images and annotations.",
    },
    "hadr": {
        "group": "hand",
        "license": "CC BY-SA 4.0",
        "url": "https://www.kaggle.com/datasets/alevysock/hadr-dataset-for-hands-instance-segmentation",
        "note": "Kaggle download; includes synthetic and real industrial hand data.",
    },
    "egohos": {
        "group": "interaction",
        "license": "MIT code; verify dataset terms",
        "url": "https://github.com/owenzlz/EgoHOS",
        "note": "Run the official download_datasets.sh after reviewing its terms.",
    },
    "visor": {
        "group": "interaction",
        "license": "See EPIC-KITCHENS VISOR terms",
        "url": "https://github.com/epic-kitchens/VISOR-HOS",
        "note": "Download from the official VISOR page, then convert to COCO format.",
    },
    "hoi_synth": {
        "group": "interaction",
        "license": "CC BY-NC 4.0",
        "url": "https://github.com/fpv-iplab/HOI-Synth",
        "note": "Public synthetic images and annotations are downloaded by this tool.",
    },
}


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "aegis-dataset-preparer/1.0"})
    with urlopen(request) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output)
    print(f"Downloaded {destination} ({destination.stat().st_size / 1e6:.1f} MB)")


def _kaggle(slug: str, destination: Path) -> None:
    try:
        import kagglehub
    except ImportError:
        raise SystemExit("Install Kaggle support first: pip install kagglehub")
    destination.mkdir(parents=True, exist_ok=True)
    path = Path(kagglehub.dataset_download(slug))
    print(f"Kaggle dataset cache: {path}")
    print(f"Copy or symlink the reviewed files into {destination}")


def _download_hoi_synth() -> None:
    target = DATA / "hoi_synth"
    _download(
        "https://iplab.dmi.unict.it/sharing/hoi-synth/annotations.zip",
        target / "annotations.zip",
    )
    _download(
        "https://iplab.dmi.unict.it/sharing/hoi-synth/images.zip",
        target / "images.zip",
    )
    print("Extract the two archives into datasets/public/hoi_synth/ before conversion.")


def _prepare_sih() -> None:
    for split in ("train", "val"):
        (ROOT / "datasets" / "objects" / "images" / split).mkdir(parents=True, exist_ok=True)
        (ROOT / "datasets" / "objects" / "labels" / split).mkdir(parents=True, exist_ok=True)
    print("Created datasets/objects/{images,labels}/{train,val}.")
    print("Add reviewed SIH images and YOLO labels; do not commit private footage.")


def _cleanup(remove_kaggle_cache: bool) -> None:
    """Delete only data created by this downloader, never the whole runtime."""
    if DATA.exists():
        shutil.rmtree(DATA)
        print(f"Deleted {DATA}")
    if remove_kaggle_cache and KAGGLE_CACHE.exists():
        shutil.rmtree(KAGGLE_CACHE)
        print(f"Deleted Kaggle cache {KAGGLE_CACHE}")
    print("Scoped cleanup complete. Other /content files were left untouched.")


def _show_plan(selected: list[str]) -> None:
    print("Dataset plan:")
    for name in selected:
        item = DATASETS[name]
        print(f"  {name}: {item['license']} - {item['url']}")
        print(f"    {item['note']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare public AEGIS pretraining datasets")
    parser.add_argument("--group", choices=("hand", "interaction", "all"), default="all")
    parser.add_argument("--datasets", help="comma-separated names; overrides --group")
    parser.add_argument("--accept-licenses", action="store_true",
                        help="confirm that you reviewed each dataset's terms")
    parser.add_argument("--kaggle", action="store_true",
                        help="download Kaggle datasets with an authenticated kagglehub session")
    parser.add_argument("--prepare-sih", action="store_true",
                        help="create private custom SIH dataset directories")
    parser.add_argument("--cleanup", action="store_true",
                        help="delete datasets/public only")
    parser.add_argument("--cleanup-kaggle", action="store_true",
                        help="also delete the KaggleHub cache")
    args = parser.parse_args(argv)

    if args.cleanup or args.cleanup_kaggle:
        _cleanup(args.cleanup_kaggle)
        if not args.datasets and args.group == "all" and not args.kaggle and not args.prepare_sih:
            return 0

    if args.datasets:
        selected = [name.strip() for name in args.datasets.split(",") if name.strip()]
        unknown = sorted(set(selected) - set(DATASETS))
        if unknown:
            raise SystemExit(f"unknown dataset(s): {', '.join(unknown)}")
    else:
        selected = [name for name, item in DATASETS.items()
                    if args.group != "all" and item["group"] == args.group]
    if not selected:
        raise SystemExit("select datasets with --datasets, or use --group hand/interaction")
    _show_plan(selected)
    if not args.accept_licenses:
        raise SystemExit("Review the listed terms, then rerun with --accept-licenses")

    if "hoi_synth" in selected:
        _download_hoi_synth()
    if args.kaggle and "hagrid" in selected:
        _kaggle("kapitanov/hagrid", DATA / "hagrid")
    if args.kaggle and "hadr" in selected:
        _kaggle("alevysock/hadr-dataset-for-hands-instance-segmentation", DATA / "hadr")
    if args.prepare_sih:
        _prepare_sih()

    print("\nManual datasets:")
    for name in selected:
        if name in ("hagrid", "hadr", "hoi_synth"):
            continue
        print(f"  {name}: see {DATASETS[name]['url']} ({DATASETS[name]['note']})")
    print("\nNext: convert annotations into the project-specific training format and keep a held-out SIH test set.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())