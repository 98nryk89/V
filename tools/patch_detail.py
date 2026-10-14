"""A2.5: 拡大版イラストの細部を、全身の高解像度画像へ位置合わせして上書きする。

全身版は元の解像度が低く、顔・フクロウ・クリスタルなどの細部が拡大で崩れる。
拡大版（バストアップ）は同じ部分を約 2.8 倍の情報量で描いているので、特徴点で位置を合わせて
（拡大・回転・平行移動のみ）重ね、境目はぼかしてなじませる。

使い方:
    python tools/patch_detail.py art/work/fullbody_x4_rgba.png art/work/bustup_x4_rgba.png \
        art/work/fullbody_x4_patched.png [--margin 160 --feather 120 --bottom 0.93]

--margin   拡大版の画像の端から、この幅（px, 全身側の座標）は使わない（画像の端で切れている部分を避ける）
--feather  境目をなじませる幅（px）
--bottom   拡大版の下からどこまでを使うか（0〜1、拡大版の高さに対する割合）
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

WORK = 1024  # 特徴点を探すときの長辺


def _gray_small(rgba: np.ndarray) -> tuple[np.ndarray, float]:
    h, w = rgba.shape[:2]
    s = WORK / max(h, w)
    small = cv2.resize(rgba[..., :3], (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(small, cv2.COLOR_RGB2GRAY), s


def estimate_transform(base: np.ndarray, detail: np.ndarray, base_roi: tuple[int, int, int, int] | None = None):
    """detail → base の相似変換 (2x3) と、インライア数・誤差を返す。"""
    gb, sb = _gray_small(base)
    gd, sd = _gray_small(detail)
    # 全身側は、特徴点を探す範囲を絞ると誤対応が減る（拡大版に写る範囲）
    if base_roi is not None:
        x0, y0, x1, y1 = (int(v * sb) for v in base_roi)
        mask = np.zeros_like(gb)
        mask[y0:y1, x0:x1] = 255
    else:
        mask = None
    sift = cv2.SIFT_create(nfeatures=8000)
    kb, db = sift.detectAndCompute(gb, mask)
    kd, dd = sift.detectAndCompute(gd, None)
    matches = cv2.BFMatcher().knnMatch(dd, db, k=2)
    good = [m for m, n in (p for p in matches if len(p) == 2) if m.distance < 0.75 * n.distance]
    if len(good) < 10:
        raise RuntimeError(f"対応点が足りない ({len(good)})")
    src = np.float32([kd[m.queryIdx].pt for m in good]) / sd
    dst = np.float32([kb[m.trainIdx].pt for m in good]) / sb
    M, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=4.0 / sb)
    if M is None:
        raise RuntimeError("位置合わせに失敗")
    inl = inl.ravel().astype(bool)
    proj = src[inl] @ M[:, :2].T + M[:, 2]
    err = float(np.median(np.linalg.norm(proj - dst[inl], axis=1)))
    return M, int(inl.sum()), len(good), err


def build_mask(detail_shape, M, base_shape, margin: int, feather: int, bottom: float) -> np.ndarray:
    dh, dw = detail_shape[:2]
    bh, bw = base_shape[:2]
    scale = float(np.hypot(*M[:, 0]))
    m_det = margin / scale  # 拡大版側の座標での余白
    region = np.zeros((dh, dw), np.float32)
    # 上端は頭の上が背景なので余白不要。左右と下端は画像の端で切れているので余白を取る
    region[: max(int(dh * bottom - m_det), 0), int(m_det) : int(dw - m_det)] = 1.0
    warped = cv2.warpAffine(region, M, (bw, bh), flags=cv2.INTER_LINEAR)
    if feather > 0:
        warped = cv2.GaussianBlur(warped, (0, 0), sigmaX=feather / 2.5)
        # ぼかしで拡大版の範囲外に広がった分を切る
        inside = cv2.warpAffine(np.ones((dh, dw), np.float32), M, (bw, bh), flags=cv2.INTER_NEAREST)
        warped *= inside
    return np.clip(warped, 0, 1)


def match_color(detail: np.ndarray, base: np.ndarray, weight: np.ndarray) -> np.ndarray:
    """重なる部分の平均・分散を全身側にそろえる（境目の色ずれ防止）。"""
    sel = (weight > 0.5) & (detail[..., 3] > 250) & (base[..., 3] > 250)
    out = detail.astype(np.float32).copy()
    if sel.sum() < 1000:
        return out
    for c in range(3):
        d, b = out[..., c][sel], base[..., c][sel].astype(np.float32)
        out[..., c] = (out[..., c] - d.mean()) * (b.std() / max(d.std(), 1e-3)) + b.mean()
    return np.clip(out, 0, 255)


def composite(base: np.ndarray, detail_warped: np.ndarray, mask: np.ndarray) -> np.ndarray:
    m = mask[..., None]
    out = base.astype(np.float32).copy()
    da = detail_warped[..., 3:4].astype(np.float32) / 255
    ba = base[..., 3:4].astype(np.float32) / 255
    alpha = m * da + (1 - m) * ba
    pre = m * detail_warped[..., :3] * da + (1 - m) * base[..., :3] * ba
    out[..., :3] = np.where(alpha > 1e-4, pre / np.maximum(alpha, 1e-4), 0)
    out[..., 3:4] = alpha * 255
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("base", type=Path)
    ap.add_argument("detail", type=Path)
    ap.add_argument("dst", type=Path)
    ap.add_argument("--margin", type=int, default=160)
    ap.add_argument("--feather", type=int, default=120)
    ap.add_argument("--bottom", type=float, default=0.93)
    ap.add_argument("--no-color-match", action="store_true")
    ap.add_argument("--mask-out", type=Path, help="上書き範囲のマスクを保存（確認用）")
    args = ap.parse_args(argv)

    base = np.asarray(Image.open(args.base).convert("RGBA"))
    detail = np.asarray(Image.open(args.detail).convert("RGBA"))
    M, inliers, total, err = estimate_transform(base, detail)
    scale = float(np.hypot(*M[:, 0]))
    angle = float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))
    print(f"位置合わせ: 対応点 {inliers}/{total}, 誤差中央値 {err:.1f}px, 倍率 {scale:.3f}, 回転 {angle:.2f}°")

    bh, bw = base.shape[:2]
    warped = cv2.warpAffine(detail, M, (bw, bh), flags=cv2.INTER_LANCZOS4, borderValue=(0, 0, 0, 0))
    mask = build_mask(detail.shape, M, base.shape, args.margin, args.feather, args.bottom)
    if not args.no_color_match:
        warped = np.concatenate([match_color(warped, base, mask), warped[..., 3:4]], axis=-1)
    out = composite(base, warped, mask)

    args.dst.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out, "RGBA").save(args.dst)
    if args.mask_out:
        Image.fromarray((mask * 255).astype(np.uint8)).save(args.mask_out)
    print(f"{args.dst}: {bw}x{bh}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
