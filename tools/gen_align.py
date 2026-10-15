"""B-0: 生成した差分を、作業キャンバス（2 倍）に位置合わせして保存する。顔まわりは AI 拡大で鮮明にする。

生成 AI の出力は元の絵より少しぼやけ、また拡大率も違うので、
  1. 元の絵（1 倍）に対する相似変換を特徴点で求める
  2. 顔まわり（とフクロウの目）だけ切り抜いて Real-ESRGAN で 4 倍にする
  3. 作業キャンバス（2 倍）へ変形して重ねる
出力: art/gen/aligned_x2/<正規化した名前>.png（2288x2750, RGBA）と _report.json

使い方:
    python tools/gen_align.py --weights RealESRGAN_x4plus_anime_6B.pth
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch_detail import estimate_transform  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "art/gen/input/upper_full.png"
K = 2
DETAIL_BOX = (250, 170, 780, 530)  # 鮮明にする範囲（元の絵の 1 倍座標）: 顔・髪飾り・フクロウの顔
SKIP = {"everymouthinterior", "owlonly"}  # 元の絵と構図が違うもの


def norm(name: str) -> str:
    s = name.lower().replace("ルナリス", "")
    return "".join(ch for ch in s if ch.isalnum())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gen", type=Path, default=ROOT / "art/gen/output")
    ap.add_argument("--out", type=Path, default=ROOT / "art/gen/aligned_x2")
    ap.add_argument("--weights", type=Path, required=True)
    ap.add_argument("--size", type=int, nargs=2, default=(2288, 2750))
    ap.add_argument("--only", nargs="*", help="この名前（正規化後）だけ処理する")
    args = ap.parse_args(argv)

    from upscale import load_model, upscale

    model, scale = load_model(args.weights)
    ref1 = np.array(Image.open(REF).convert("RGBA"))
    W, H = args.size
    args.out.mkdir(parents=True, exist_ok=True)
    rep_path = args.out / "_report.json"
    report = json.loads(rep_path.read_text()) if rep_path.exists() else {}

    for f in sorted(glob.glob(str(args.gen / "*"))):
        if not f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            continue
        key = norm(Path(f).stem)
        if key in SKIP or (args.only and key not in args.only):
            continue
        dst = args.out / f"{key}.png"
        if dst.exists() and not args.only:
            continue
        t0 = time.time()
        g = np.array(Image.open(f).convert("RGB"))
        M, inl, tot, err = estimate_transform(np.array(Image.open(REF).convert("RGBA")), np.dstack([g, np.full(g.shape[:2], 255, np.uint8)]))
        # 全体: そのまま変形
        full = cv2.warpAffine(g, M * K, (W, H), flags=cv2.INTER_LANCZOS4, borderValue=(255, 255, 255))
        # 顔まわり: 生成画像の座標で切り抜いて 4 倍にし、変形して上書き
        Minv = cv2.invertAffineTransform(M)
        x0, y0, x1, y1 = DETAIL_BOX
        corners = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], np.float32)
        gc = corners @ Minv[:, :2].T + Minv[:, 2]
        cx0, cy0 = np.floor(gc.min(0)).astype(int)
        cx1, cy1 = np.ceil(gc.max(0)).astype(int)
        cx0, cy0 = max(cx0, 0), max(cy0, 0)
        cx1, cy1 = min(cx1, g.shape[1]), min(cy1, g.shape[0])
        crop = g[cy0:cy1, cx0:cx1].astype(np.float32) / 255.0
        up = (upscale(crop, model, scale) * 255.0 + 0.5).astype(np.uint8)
        A = M[:, :2] * K / scale
        t = K * (M[:, :2] @ np.array([cx0, cy0], np.float64) + M[:, 2])
        M2 = np.hstack([A, t[:, None]])
        sharp = cv2.warpAffine(up, M2, (W, H), flags=cv2.INTER_AREA if A[0, 0] < 1 else cv2.INTER_LANCZOS4, borderValue=(0, 0, 0))
        cover = cv2.warpAffine(np.ones(up.shape[:2], np.float32), M2, (W, H), flags=cv2.INTER_LINEAR)
        cover = cv2.erode(cover, np.ones((9, 9), np.uint8))
        cover = cv2.GaussianBlur(cover, (0, 0), 3)[..., None]
        out = (sharp * cover + full * (1 - cover)).astype(np.uint8)
        Image.fromarray(out).save(dst)
        report[key] = {"source": Path(f).name, "inliers": int(inl), "total": int(tot), "err_px_1x": round(float(err), 2),
                       "scale": round(float(np.hypot(*M[:, 0])), 4)}
        rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=1))
        print(f"{key}: 誤差 {err:.2f}px ({time.time() - t0:.0f}s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
