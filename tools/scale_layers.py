"""全レイヤーを同じ倍率で縮小（または拡大）する。iki の読み込み上限（アトラス 12MB など）に収めるため。

使い方:
    python tools/scale_layers.py art/parts/upper art/parts/upper_s 0.94
透過の縁に色がにじまないよう、乗算済みアルファで縮小する。
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def scale_rgba(arr: np.ndarray, f: float, size: tuple[int, int] | None = None) -> np.ndarray:
    a = arr[..., 3:4].astype(np.float32) / 255.0
    pre = np.concatenate([arr[..., :3].astype(np.float32) * a, a * 255.0], axis=-1)
    h, w = arr.shape[:2]
    nw, nh = size or (round(w * f), round(h * f))
    interp = cv2.INTER_AREA if nw < w else cv2.INTER_CUBIC
    r = cv2.resize(pre, (nw, nh), interpolation=interp)
    ra = r[..., 3:4] / 255.0
    rgb = np.where(ra > 1e-4, r[..., :3] / np.maximum(ra, 1e-4), 0)
    return np.clip(np.concatenate([rgb, r[..., 3:4]], axis=-1) + 0.5, 0, 255).astype(np.uint8)


def main() -> int:
    src, dst, f = Path(sys.argv[1]), Path(sys.argv[2]), float(sys.argv[3])
    dst.mkdir(parents=True, exist_ok=True)
    first = None
    for p in sorted(src.glob("*.png")):
        arr = np.array(Image.open(p).convert("RGBA"))
        if first is None:
            first = (round(arr.shape[1] * f) // 2 * 2, round(arr.shape[0] * f) // 2 * 2)  # 偶数にそろえる
        Image.fromarray(scale_rgba(arr, f, first), "RGBA").save(dst / p.name)
    print(f"{src} -> {dst} x{f} ({first[0]}x{first[1]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
