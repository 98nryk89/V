import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import patch_detail as pd  # noqa: E402


def _scene(h, w, seed=0):
    """特徴点が取れるランダムな図形の絵（RGBA）。"""
    rng = np.random.default_rng(seed)
    img = np.full((h, w, 3), 255, np.uint8)
    for _ in range(400):
        c = tuple(int(v) for v in rng.integers(0, 255, 3))
        x, y = int(rng.integers(0, w)), int(rng.integers(0, h))
        cv2.circle(img, (x, y), int(rng.integers(3, 25)), c, -1)
        cv2.line(img, (x, y), (int(rng.integers(0, w)), int(rng.integers(0, h))), c, 2)
    return np.concatenate([img, np.full((h, w, 1), 255, np.uint8)], axis=-1)


def test_alignment_recovers_scale_and_offset():
    hi = _scene(1600, 1200)
    # base: 全体を 1/2 に縮小（解像度が低い全身版の代わり）
    base = cv2.resize(hi, (600, 800), interpolation=cv2.INTER_AREA)
    # detail: 上半分を切り出した高解像度版（拡大版の代わり）
    detail = hi[100:900, 200:1000]
    M, inl, total, err = pd.estimate_transform(base, detail)
    assert inl > 50
    assert abs(np.hypot(*M[:, 0]) - 0.5) < 0.01
    assert abs(M[0, 2] - 100) < 2 and abs(M[1, 2] - 50) < 2
    assert err < 1.5


def test_composite_uses_detail_inside_mask_and_base_outside():
    base = np.zeros((10, 10, 4), np.uint8)
    base[...] = (10, 10, 10, 255)
    det = np.zeros((10, 10, 4), np.uint8)
    det[...] = (200, 200, 200, 255)
    mask = np.zeros((10, 10), np.float32)
    mask[:, :5] = 1
    out = pd.composite(base, det, mask)
    assert tuple(out[0, 0]) == (200, 200, 200, 255)
    assert tuple(out[0, 9]) == (10, 10, 10, 255)


def test_composite_takes_detail_alpha():
    base = np.zeros((4, 4, 4), np.uint8)  # 全身側では透明（例: 拡大版だけ耳飾りが長い）
    det = np.zeros((4, 4, 4), np.uint8)
    det[...] = (0, 0, 255, 255)
    out = pd.composite(base, det, np.ones((4, 4), np.float32))
    assert tuple(out[1, 1]) == (0, 0, 255, 255)
