"""Visualize full-rotation augmentation for a sample image."""

import argparse
import importlib
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--output", type=Path, default=Path("rotation_check.jpg"))
    args = parser.parse_args()
    cv2 = importlib.import_module("cv2")

    image = cv2.imread(str(args.image))
    if image is None:
        raise FileNotFoundError(args.image)
    height, width = image.shape[:2]
    canvas = cv2.copyMakeBorder(
        image, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=(24, 24, 24)
    )
    tiles = []
    for angle in range(0, 360, 45):
        matrix = cv2.getRotationMatrix2D((width / 2 + 20, height / 2 + 20), angle, 1.0)
        tiles.append(cv2.warpAffine(canvas, matrix, (width + 40, height + 40)))
    cv2.imwrite(str(args.output), cv2.hconcat(tiles[:4]))
    cv2.imwrite(
        str(args.output.with_name(args.output.stem + "_2" + args.output.suffix)),
        cv2.hconcat(tiles[4:]),
    )


if __name__ == "__main__":
    main()
