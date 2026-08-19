#!/usr/bin/env python3
"""Validate that an Open Teach LIBERO demonstration contains usable streams."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import h5py
import numpy as np


def inspect_h5(path: Path) -> tuple[dict[str, tuple[int, ...]], bool]:
    shapes: dict[str, tuple[int, ...]] = {}
    valid = True
    with h5py.File(path, "r") as handle:
        for name, dataset in handle.items():
            shapes[name] = tuple(dataset.shape)
            if dataset.shape and dataset.shape[0] == 0:
                valid = False
            if np.issubdtype(dataset.dtype, np.number) and not np.isfinite(dataset[:]).all():
                valid = False
    return shapes, valid


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("demo", type=Path)
    args = parser.parse_args()
    demo = args.demo.expanduser().resolve()
    if not demo.is_dir():
        raise SystemExit(f"Not a demonstration directory: {demo}")

    valid = True
    h5_files = sorted(demo.glob("*.h5"))
    avi_files = sorted(demo.glob("*.avi"))
    if not h5_files or not avi_files:
        valid = False

    for path in h5_files:
        try:
            shapes, file_valid = inspect_h5(path)
        except OSError as error:
            print(f"H5 {path.name}: unreadable ({error})")
            valid = False
            continue
        print(f"H5 {path.name}: {shapes}")
        valid &= file_valid

    for path in avi_files:
        capture = cv2.VideoCapture(str(path))
        frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        ok, first = capture.read()
        capture.release()
        file_valid = frames > 0 and width > 0 and height > 0 and ok and first is not None
        print(f"AVI {path.name}: frames={frames} size={width}x{height} readable={ok}")
        valid &= file_valid

    if not valid:
        raise SystemExit("Demonstration validation FAILED")
    print("Demonstration validation PASSED")


if __name__ == "__main__":
    main()
