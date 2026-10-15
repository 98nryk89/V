"""作業用: 画像の一部を拡大し、座標入りのグリッドを重ねて保存する（パーツの位置を読み取るため）。

使い方:
    python tools/viewgrid.py art/work/upper_x4_rgba.png out.png --box 380 200 760 520 --scale 3 --step 20 --unit 4
--box は元の絵（1x）の座標。--unit は画像が 1x の何倍か（4x 画像なら 4）。
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path)
    ap.add_argument("dst", type=Path)
    ap.add_argument("--box", type=int, nargs=4, required=True, metavar=("X0", "Y0", "X1", "Y1"))
    ap.add_argument("--scale", type=float, default=3.0, help="表示倍率（1x 座標に対して）")
    ap.add_argument("--step", type=int, default=20)
    ap.add_argument("--unit", type=float, default=4.0)
    ap.add_argument("--bg", default="#3aa655")
    a = ap.parse_args()

    im = Image.open(a.src).convert("RGBA")
    x0, y0, x1, y1 = a.box
    crop = im.crop(tuple(int(v * a.unit) for v in a.box))
    w, h = int((x1 - x0) * a.scale), int((y1 - y0) * a.scale)
    crop = crop.resize((w, h), Image.LANCZOS)
    bg = Image.new("RGBA", crop.size, a.bg)
    bg.alpha_composite(crop)
    d = ImageDraw.Draw(bg)
    for gx in range((x0 // a.step + 1) * a.step, x1, a.step):
        X = (gx - x0) * a.scale
        d.line([(X, 0), (X, h)], fill=(255, 255, 0, 110), width=1)
        d.text((X + 2, 2), str(gx), fill=(255, 255, 255, 255))
    for gy in range((y0 // a.step + 1) * a.step, y1, a.step):
        Y = (gy - y0) * a.scale
        d.line([(0, Y), (w, Y)], fill=(255, 255, 0, 110), width=1)
        d.text((2, Y + 2), str(gy), fill=(255, 255, 255, 255))
    bg.convert("RGB").save(a.dst)


if __name__ == "__main__":
    main()
