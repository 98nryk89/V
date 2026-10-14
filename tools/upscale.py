"""A1: Real-ESRGAN (アニメ用) で元絵を 4 倍に拡大する。CPU でも動く（タイル処理）。

使い方:
    python tools/upscale.py art/reference/fullbody.webp art/work/fullbody_x4.png \
        --weights path/to/RealESRGAN_x4plus_anime_6B.pth

重み: https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from spandrel import ModelLoader


def load_model(weights: Path):
    # weights_only=True: pickle 内の任意コードを実行しない
    state = torch.load(weights, map_location="cpu", weights_only=True)
    if isinstance(state, dict) and "params_ema" in state:
        state = state["params_ema"]
    desc = ModelLoader().load_from_state_dict(state)
    return desc.model.eval(), desc.scale


@torch.inference_mode()
def upscale(img: np.ndarray, model, scale: int, tile: int = 256, pad: int = 16) -> np.ndarray:
    """img: HxWx3 float32 0..1 -> (H*scale)x(W*scale)x3"""
    h, w, _ = img.shape
    out = np.zeros((h * scale, w * scale, 3), dtype=np.float32)
    x = torch.from_numpy(img).permute(2, 0, 1)[None]
    for y0 in range(0, h, tile):
        for x0 in range(0, w, tile):
            y1, x1 = min(y0 + tile, h), min(x0 + tile, w)
            py0, px0 = max(y0 - pad, 0), max(x0 - pad, 0)
            py1, px1 = min(y1 + pad, h), min(x1 + pad, w)
            res = model(x[:, :, py0:py1, px0:px1])[0].permute(1, 2, 0).clamp(0, 1).numpy()
            oy, ox = (y0 - py0) * scale, (x0 - px0) * scale
            out[y0 * scale : y1 * scale, x0 * scale : x1 * scale] = res[
                oy : oy + (y1 - y0) * scale, ox : ox + (x1 - x0) * scale
            ]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src", type=Path)
    ap.add_argument("dst", type=Path)
    ap.add_argument("--weights", type=Path, required=True)
    ap.add_argument("--tile", type=int, default=256)
    args = ap.parse_args(argv)

    model, scale = load_model(args.weights)
    img = np.asarray(Image.open(args.src).convert("RGB"), dtype=np.float32) / 255.0
    t = time.time()
    out = upscale(img, model, scale, args.tile)
    args.dst.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray((out * 255.0 + 0.5).astype(np.uint8)).save(args.dst)
    print(f"{args.src} {img.shape[1]}x{img.shape[0]} -> {args.dst} {out.shape[1]}x{out.shape[0]} ({time.time() - t:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
