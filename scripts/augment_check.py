"""Create a contact sheet showing full-orientation augmentation candidates."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize 0–360 degree image rotations.")
    parser.add_argument("image", type=Path)
    parser.add_argument("--output", type=Path, default=Path("augmentation_check.jpg"))
    parser.add_argument("--samples", type=int, default=12)
    args = parser.parse_args()
    import cv2
    import numpy as np

    image = cv2.imread(str(args.image))
    if image is None:
        raise FileNotFoundError(args.image)
    height, width = image.shape[:2]
    center = (width / 2, height / 2)
    tiles = []
    for angle in np.linspace(0, 360, args.samples, endpoint=False):
        matrix = cv2.getRotationMatrix2D(center, float(angle), 1.0)
        tile = cv2.warpAffine(image, matrix, (width, height), borderMode=cv2.BORDER_REFLECT)
        cv2.putText(tile, f"{angle:.0f} deg", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        tiles.append(tile)
    columns = 4
    while len(tiles) % columns:
        tiles.append(np.zeros_like(image))
    cv2.imwrite(str(args.output), np.vstack([np.hstack(tiles[index:index + columns]) for index in range(0, len(tiles), columns)]))


if __name__ == "__main__":
    main()
