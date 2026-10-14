"""A2: アニメ用セグメンテーション (ISNet-anime) で背景を透過する。

使い方:
    python tools/remove_bg.py art/work/fullbody_x4.png art/work/fullbody_x4_rgba.png \
        --model path/to/isnet-anime.onnx [--mask-src art/reference/fullbody.webp]

--mask-src を指定すると、マスク推定はその画像（元絵）で行い、出力画像の解像度に拡大して適用する。
重み: https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-anime.onnx
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageFilter

SIZE = 1024
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)


def predict_mask(img: Image.Image, session: ort.InferenceSession) -> Image.Image:
    x = np.asarray(img.convert("RGB").resize((SIZE, SIZE), Image.LANCZOS), dtype=np.float32)
    x = x / max(float(x.max()), 1e-6) - MEAN
    x = x.transpose(2, 0, 1)[None]
    pred = session.run(None, {session.get_inputs()[0].name: x})[0][0, 0]
    pred = (pred - pred.min()) / max(float(pred.max() - pred.min()), 1e-6)
    return Image.fromarray((pred * 255).astype(np.uint8)).resize(img.size, Image.LANCZOS)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src", type=Path)
    ap.add_argument("dst", type=Path)
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--mask-src", type=Path)
    args = ap.parse_args(argv)

    session = ort.InferenceSession(str(args.model), providers=["CPUExecutionProvider"])
    img = Image.open(args.src).convert("RGB")
    mask = predict_mask(Image.open(args.mask_src or args.src), session)
    mask = mask.resize(img.size, Image.LANCZOS).filter(ImageFilter.GaussianBlur(1))
    out = img.copy()
    out.putalpha(mask)
    args.dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(args.dst)
    print(f"{args.dst}: {img.size[0]}x{img.size[1]} RGBA")
    return 0


if __name__ == "__main__":
    sys.exit(main())
