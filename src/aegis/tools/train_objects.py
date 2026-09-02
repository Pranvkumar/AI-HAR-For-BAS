"""Ground-side tooling for the Tier-2 object detector.

Nothing in this module runs on the payload side. Training needs PyTorch and
Ultralytics; inference needs neither, because the deliverable is an ONNX file
that ``perception/objects.py`` loads through onnxruntime. Keeping that split
strict is what lets the runtime install stay small and offline.

Four subcommands, in the order you will use them::

    python -m aegis.tools.train_objects grab    --source 1 --every 10
    python -m aegis.tools.train_objects autolabel --prompts "red box,blue box"
    python -m aegis.tools.train_objects train   --epochs 80
    python -m aegis.tools.train_objects export

``autolabel`` is where an open-vocabulary model earns its place. YOLO-World and
Grounding DINO generalise to unseen categories from a text prompt, which makes
them excellent *annotators* and poor *verifiers*: they ground nouns well and
attributes ("red" vs "blue") badly, which is precisely the discrimination this
system needs at runtime. So they draw the first-pass boxes, a human fixes the
labels, and a small closed-set YOLO learns the distinction properly.

Expected layout under ``datasets/objects/``::

    images/train/*.jpg      frames to learn from
    images/val/*.jpg        held-out frames
    labels/train/*.txt      YOLO format: class cx cy w h  (normalised)
    labels/val/*.txt
    data.yaml               written by this tool
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import shutil
import sys

from aegis.config import project_root


DEFAULT_ROOT = "datasets/objects"
DEFAULT_MODEL = "models/objects/objects.onnx"
CANONICAL_CLASSES = [
    "outer_container",
    "container_lid",
    "red_box",
    "blue_box",
    "astronaut_hand",
]


# ================================================================== helpers ===

def _dataset_dir(root: Path, relative: str) -> Path:
    path = Path(relative)
    return path if path.is_absolute() else root / path


def _require(module: str, install_hint: str):
    try:
        return __import__(module)
    except ImportError:
        sys.exit(
            f"\n'{module}' is not installed.\n"
            f"  {install_hint}\n\n"
            "This is a ground-side tool only -- the runtime does not need it.\n"
        )


def write_data_yaml(dataset: Path, names: list[str]) -> Path:
    """Write the Ultralytics dataset descriptor."""
    path = dataset / "data.yaml"
    lines = [
        f"path: {dataset.as_posix()}",
        "train: images/train",
        "val: images/val",
        "",
        f"nc: {len(names)}",
        "names:",
    ]
    lines += [f"  {i}: {name}" for i, name in enumerate(names)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def read_names(dataset: Path) -> list[str]:
    """Recover the class list from data.yaml, or from a plain classes.txt."""
    classes_txt = dataset / "classes.txt"
    if classes_txt.exists():
        names = [ln.strip() for ln in classes_txt.read_text(encoding="utf-8").splitlines()]
        return [n for n in names if n]

    data_yaml = dataset / "data.yaml"
    if data_yaml.exists():
        import yaml
        raw = yaml.safe_load(data_yaml.read_text(encoding="utf-8")) or {}
        names = raw.get("names")
        if isinstance(names, dict):
            return [names[k] for k in sorted(names, key=lambda x: int(x))]
        if isinstance(names, list):
            return [str(n) for n in names]
    return []


def _resolve_device(torch, requested: str) -> str:
    """Use CUDA when requested implicitly and fall back cleanly on CPU."""
    if requested != "auto":
        return requested
    return "0" if torch.cuda.is_available() else "cpu"


# ================================================================= commands ===

def cmd_grab(args) -> int:
    """Pull frames out of a camera or video file for labelling."""
    cv2 = _require("cv2", "pip install opencv-python")

    root = project_root()
    dataset = _dataset_dir(root, args.dataset)
    out = dataset / "images" / "train"
    out.mkdir(parents=True, exist_ok=True)

    source: object = args.source
    if isinstance(source, str) and source.isdigit():
        source = int(source)

    capture = cv2.VideoCapture(source)
    if not capture.isOpened():
        sys.exit(f"could not open source: {args.source}")

    existing = len(list(out.glob("*.jpg")))
    grabbed, index = 0, 0
    print(f"Grabbing every {args.every} frames from {args.source} -> {out}")
    print("Move the objects between shots: different angles, distances, lighting,")
    print("partial occlusion by your hand. Press Q in the preview window to stop.\n")

    try:
        while grabbed < args.count:
            ok, frame = capture.read()
            if not ok:
                break
            if index % args.every == 0:
                name = out / f"frame_{existing + grabbed:05d}.jpg"
                cv2.imwrite(str(name), frame)
                grabbed += 1
                print(f"  [{grabbed}/{args.count}] {name.name}", end="\r")
            index += 1
            if args.preview:
                cv2.imshow("grab (Q to stop)", frame)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    break
    finally:
        capture.release()
        if args.preview:
            cv2.destroyAllWindows()

    print(f"\nSaved {grabbed} frames to {out}")
    print("Next: label them, or run the 'autolabel' subcommand for a first pass.")
    return 0


def cmd_autolabel(args) -> int:
    """First-pass boxes from an open-vocabulary detector, for a human to fix."""
    _require("ultralytics", "pip install ultralytics")
    from ultralytics import YOLOWorld

    root = project_root()
    dataset = _dataset_dir(root, args.dataset)
    images = dataset / "images" / "train"
    labels = dataset / "labels" / "train"
    labels.mkdir(parents=True, exist_ok=True)

    prompts = [p.strip() for p in args.prompts.split(",") if p.strip()]
    names = [p.replace(" ", "_") for p in prompts]
    if not prompts:
        sys.exit("--prompts is required, e.g. --prompts 'red box,blue box,tray'")

    frames = sorted(images.glob("*.jpg"))
    if not frames:
        sys.exit(f"no images in {images} -- run the 'grab' subcommand first")

    print(f"Auto-labelling {len(frames)} frames with prompts: {prompts}")
    print("\n  These boxes are a STARTING POINT, not ground truth. Open-vocabulary")
    print("  models confuse colour attributes -- expect 'red box' and 'blue box'")
    print("  to be swapped often. Review every frame before training.\n")

    model = YOLOWorld(args.weights)
    model.set_classes(prompts)

    written = 0
    for frame in frames:
        results = model.predict(str(frame), conf=args.confidence, verbose=False)
        rows: list[str] = []
        for result in results:
            height, width = result.orig_shape
            for box in result.boxes:
                cls = int(box.cls.item())
                x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
                cx = ((x1 + x2) / 2) / width
                cy = ((y1 + y2) / 2) / height
                bw = (x2 - x1) / width
                bh = (y2 - y1) / height
                rows.append(f"{cls} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
        (labels / f"{frame.stem}.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
        written += 1
        print(f"  [{written}/{len(frames)}] {frame.name}: {len(rows)} boxes", end="\r")

    (dataset / "classes.txt").write_text("\n".join(names) + "\n", encoding="utf-8")
    write_data_yaml(dataset, names)
    print(f"\n\nWrote {written} label files and data.yaml")
    print("Now REVIEW them (labelImg, Label Studio or CVAT all read this format),")
    print("then run: python -m aegis.tools.train_objects split")
    return 0


def cmd_split(args) -> int:
    """Move a fraction of labelled frames into the validation set."""
    root = project_root()
    dataset = _dataset_dir(root, args.dataset)
    for sub in ("images/val", "labels/val"):
        (dataset / sub).mkdir(parents=True, exist_ok=True)

    frames = sorted((dataset / "images" / "train").glob("*.jpg"))
    labelled = [f for f in frames if (dataset / "labels" / "train" / f"{f.stem}.txt").exists()]
    if not labelled:
        sys.exit("no labelled frames found -- label them before splitting")

    random.seed(args.seed)
    random.shuffle(labelled)
    count = max(1, int(len(labelled) * args.fraction))
    moved = 0
    for frame in labelled[:count]:
        label = dataset / "labels" / "train" / f"{frame.stem}.txt"
        shutil.move(str(frame), dataset / "images" / "val" / frame.name)
        shutil.move(str(label), dataset / "labels" / "val" / label.name)
        moved += 1

    print(f"Moved {moved} of {len(labelled)} labelled frames into the validation set.")
    print(f"Train: {len(labelled) - moved}   Val: {moved}")
    return 0


def cmd_train(args) -> int:
    """Fine-tune a small YOLO on the labelled frames."""
    _require("ultralytics", "pip install ultralytics")
    from ultralytics import YOLO
    import torch

    root = project_root()
    dataset = _dataset_dir(root, args.dataset)
    names = read_names(dataset)
    if not names:
        sys.exit(f"no class names found in {dataset} (expected data.yaml or classes.txt)")

    data_yaml = dataset / "data.yaml"
    if not data_yaml.exists():
        data_yaml = write_data_yaml(dataset, names)

    device = _resolve_device(torch, args.device)
    missing = [name for name in CANONICAL_CLASSES if name not in names]
    if missing:
        print(f"WARNING: dataset is missing canonical classes: {missing}")
        print("  Add reviewed labels for every object that appears in the experiment before deployment.")

    print(f"Training {args.weights} on {len(names)} classes: {names}")
    print(f"  epochs={args.epochs}  imgsz={args.imgsz}  batch={args.batch}  device={device}")
    print("\n  On a 4 GB laptop GPU keep batch at 8 and imgsz at 640. If you hit")
    print("  'CUDA out of memory', halve the batch before touching anything else.\n")

    model = YOLO(args.weights)
    model.train(
        data=str(data_yaml),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=device,
        project=str(root / "artifacts" / "objects"),
        name=args.run,
        exist_ok=True,
        patience=args.patience,
    )

    best = root / "artifacts" / "objects" / args.run / "weights" / "best.pt"
    print(f"\nBest checkpoint: {best}")
    print("Next: python -m aegis.tools.train_objects export")
    return 0


def cmd_export(args) -> int:
    """Export the trained checkpoint to ONNX and install it into models/."""
    _require("ultralytics", "pip install ultralytics")
    from ultralytics import YOLO

    root = project_root()
    checkpoint = Path(args.checkpoint)
    if not checkpoint.is_absolute():
        checkpoint = root / checkpoint
    if not checkpoint.exists():
        sys.exit(f"checkpoint not found: {checkpoint}\nTrain one first, or pass --checkpoint")

    model = YOLO(str(checkpoint))
    print(f"Exporting {checkpoint.name} to ONNX (imgsz={args.imgsz}, opset={args.opset}) ...")
    exported = Path(model.export(format="onnx", imgsz=args.imgsz, opset=args.opset, simplify=True))

    destination = Path(args.out)
    if not destination.is_absolute():
        destination = root / destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(exported, destination)

    # A sidecar name list makes the export readable even if the ONNX metadata is
    # stripped by a later conversion step.
    names = getattr(model, "names", None) or {}
    if names:
        ordered = [names[k] for k in sorted(names, key=lambda x: int(x))]
        destination.with_suffix(".names.json").write_text(
            json.dumps(ordered, indent=2), encoding="utf-8"
        )

    size_mb = destination.stat().st_size / (1024 * 1024)
    print(f"\nInstalled: {destination}  ({size_mb:.1f} MB)")
    print(f"Classes:   {list(names.values()) if names else 'unnamed'}")
    print("\nNow enable it in configs/app.yaml:")
    print("    objects_enabled: true")
    print(f"    objects_model_path: {destination.relative_to(root).as_posix()}")
    print("\nAnd name the expected object on each step in configs/protocol.yaml:")
    print("    object: red_box")
    return 0


def cmd_check(args) -> int:
    """Load the installed detector and report what the runtime will see."""
    from aegis.config import load_config
    from aegis.perception.objects import build_detector

    config = load_config(args.config)
    if not config.objects_enabled:
        print("objects_enabled is false in the config -- forcing it on for this check.")
        config.objects_enabled = True

    detector = build_detector(config)
    print(f"\nDetector: {detector.describe()}")
    for key, value in detector.stats().items():
        print(f"  {key}: {value}")

    if not detector.available:
        print("\nThe runtime would fall back to Tier 0 (hands and zones only).")
        return 1

    print("\nSelf-test on a synthetic frame ...")
    import numpy as np
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    detections = detector.detect(frame)
    print(f"  inference OK, {len(detections)} detections on a blank frame")
    print(f"  mean latency: {detector.mean_latency_ms:.1f} ms")
    budget = 1000.0 / max(detector.mean_latency_ms, 1e-6)
    print(f"  detector-only ceiling: ~{budget:.0f} fps at interval=1")
    return 0


# ==================================================================== entry ===

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="train_objects",
        description="Label, train and export the Tier-2 object detector.",
    )
    parser.add_argument("--dataset", default=DEFAULT_ROOT, help="dataset root")
    sub = parser.add_subparsers(dest="command", required=True)

    grab = sub.add_parser("grab", help="capture frames for labelling")
    grab.add_argument("--source", default="0", help="camera index or video path")
    grab.add_argument("--every", type=int, default=10, help="keep every Nth frame")
    grab.add_argument("--count", type=int, default=300, help="how many to keep")
    grab.add_argument("--preview", action="store_true", help="show a preview window")
    grab.set_defaults(func=cmd_grab)

    auto = sub.add_parser("autolabel", help="first-pass boxes from YOLO-World")
    auto.add_argument(
        "--prompts",
        default=", ".join(name.replace("_", " ") for name in CANONICAL_CLASSES),
        help="comma-separated text prompts",
    )
    auto.add_argument("--weights", default="yolov8s-worldv2.pt")
    auto.add_argument("--confidence", type=float, default=0.20)
    auto.set_defaults(func=cmd_autolabel)

    split = sub.add_parser("split", help="carve out a validation set")
    split.add_argument("--fraction", type=float, default=0.2)
    split.add_argument("--seed", type=int, default=0)
    split.set_defaults(func=cmd_split)

    train = sub.add_parser("train", help="fine-tune a small YOLO")
    train.add_argument("--weights", default="yolov8n.pt")
    train.add_argument("--epochs", type=int, default=80)
    train.add_argument("--imgsz", type=int, default=640)
    train.add_argument("--batch", type=int, default=8)
    train.add_argument("--device", default="auto", help="auto, GPU index such as '0', or 'cpu'")
    train.add_argument("--patience", type=int, default=20)
    train.add_argument("--run", default="run1")
    train.set_defaults(func=cmd_train)

    export = sub.add_parser("export", help="convert to ONNX and install")
    export.add_argument("--checkpoint", default="artifacts/objects/run1/weights/best.pt")
    export.add_argument("--out", default=DEFAULT_MODEL)
    export.add_argument("--imgsz", type=int, default=640)
    export.add_argument("--opset", type=int, default=12)
    export.set_defaults(func=cmd_export)

    check = sub.add_parser("check", help="verify the installed detector loads")
    check.add_argument("--config", default=None)
    check.set_defaults(func=cmd_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
