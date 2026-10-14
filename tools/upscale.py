"""A1: Real-ESRGAN (アニメ用) で元絵を 4 倍に拡大する。CPU でも動く（タイル処理）。

透過 PNG/WebP を入れた場合は、色とアルファを別々に拡大する。透明部分の黒が縁ににじまないよう、
先に縁の色を透明部分へ広げてから拡大する。また、ほぼ不透明（250 以上）は 255 に、
ほぼ透明（2 以下）は 0 にそろえる。

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


ALPHA_SOLID, ALPHA_CLEAR = 250, 2


def clean_alpha(alpha: np.ndarray) -> np.ndarray:
    """uint8 アルファの、ほぼ不透明・ほぼ透明を確定させる。"""
    out = alpha.copy()
    out[alpha >= ALPHA_SOLID] = 255
    out[alpha <= ALPHA_CLEAR] = 0
    return out


def bleed_colors(rgb: np.ndarray, alpha: np.ndarray, iterations: int = 32) -> np.ndarray:
    """透明部分の色を、隣の不透明部分の色で埋める（拡大時の縁のにじみ防止）。"""
    rgb = rgb.copy()
    known = alpha > 0
    for _ in range(iterations):
        if known.all():
            break
        acc = np.zeros_like(rgb)
        cnt = np.zeros(known.shape, dtype=np.float32)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            k = np.roll(known, (dy, dx), axis=(0, 1))
            acc += np.roll(rgb, (dy, dx), axis=(0, 1)) * k[..., None]
            cnt += k
        grow = ~known & (cnt > 0)
        rgb[grow] = acc[grow] / cnt[grow][:, None]
        known = known | grow
    if not known.all():
        rgb[~known] = rgb[known].mean(axis=0) if known.any() else 0
    return rgb


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src", type=Path)
    ap.add_argument("dst", type=Path)
    ap.add_argument("--weights", type=Path, required=True)
    ap.add_argument("--tile", type=int, default=256)
    args = ap.parse_args(argv)

    model, scale = load_model(args.weights)
    src = Image.open(args.src)
    t = time.time()
    if "A" in src.getbands():
        rgba = np.asarray(src.convert("RGBA"))
        alpha = clean_alpha(rgba[..., 3])
        img = bleed_colors(rgba[..., :3].astype(np.float32) / 255.0, alpha)
        a3 = np.repeat((alpha.astype(np.float32) / 255.0)[..., None], 3, axis=-1)
        out_rgb = upscale(img, model, scale, args.tile)
        out_a = upscale(a3, model, scale, args.tile).mean(axis=-1)
        out_a = clean_alpha((out_a * 255.0 + 0.5).astype(np.uint8))
        out = np.concatenate([(out_rgb * 255.0 + 0.5).astype(np.uint8), out_a[..., None]], axis=-1)
        result = Image.fromarray(out, "RGBA")
    else:
        img = np.asarray(src.convert("RGB"), dtype=np.float32) / 255.0
        result = Image.fromarray((upscale(img, model, scale, args.tile) * 255.0 + 0.5).astype(np.uint8))
    args.dst.parent.mkdir(parents=True, exist_ok=True)
    result.save(args.dst)
    print(f"{args.src} {src.size[0]}x{src.size[1]} -> {args.dst} {result.size[0]}x{result.size[1]} {result.mode} ({time.time() - t:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
