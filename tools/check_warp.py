"""頭の動きの変形（tools/build_overlay_model.py の displacement）が、破綻しないかを数値で調べる。

変形の「ヤコビアン行列式」を、頭のまわりの格子で計算する。
  行列式 1 = 変化なし、0.5 = 半分に潰れる、0 以下 = 折り返し（絵が裏返る）、2 = 2 倍に伸びる。
使い方:
    python tools/check_warp.py            # アプリの上限の角度で、全組み合わせを調べる
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_overlay_model as bom  # noqa: E402

LIMITS = dict(ParamAngleX=15.0, ParamAngleY=12.0, ParamAngleZ=10.0)  # アプリで使う上限（app/src/mapping.js の ANGLE_LIMIT と同じ）


def total_disp(x, y, vals, hair_fn=None):
    dx = np.zeros_like(x)
    dy = np.zeros_like(x)
    for p, v in vals.items():
        a, b = bom.displacement(x, y, p, v, hair_fn)
        dx += a
        dy += b
    return dx, dy


def jacobian_det(vals, step=16, box=(300, 0, 1900, 1400)):
    xs = np.arange(box[0], box[2], step, dtype=np.float64)
    ys = np.arange(box[1], box[3], step, dtype=np.float64)
    X, Y = np.meshgrid(xs, ys)
    dx, dy = total_disp(X, Y, vals)
    px, py = X + dx, Y + dy
    dpx_dx = np.gradient(px, step, axis=1)
    dpx_dy = np.gradient(px, step, axis=0)
    dpy_dx = np.gradient(py, step, axis=1)
    dpy_dy = np.gradient(py, step, axis=0)
    det = dpx_dx * dpy_dy - dpx_dy * dpy_dx
    return X, Y, det, np.hypot(dx, dy)


def worst_case(limits=LIMITS):
    worst = (9.0, None, None)
    best = (0.0, None, None)
    for sx, sy, sz in itertools.product((-1, 0, 1), repeat=3):
        vals = {"ParamAngleX": sx * limits["ParamAngleX"], "ParamAngleY": sy * limits["ParamAngleY"], "ParamAngleZ": sz * limits["ParamAngleZ"]}
        X, Y, det, mag = jacobian_det(vals)
        i = np.unravel_index(np.argmin(det), det.shape)
        j = np.unravel_index(np.argmax(det), det.shape)
        if det[i] < worst[0]:
            worst = (float(det[i]), vals, (float(X[i]), float(Y[i])))
        if det[j] > best[0]:
            best = (float(det[j]), vals, (float(X[j]), float(Y[j])))
    return worst, best


if __name__ == "__main__":
    w, b = worst_case()
    print(f"最小の行列式 {w[0]:.2f} at {w[2]} {w[1]}")
    print(f"最大の行列式 {b[0]:.2f} at {b[2]} {b[1]}")
