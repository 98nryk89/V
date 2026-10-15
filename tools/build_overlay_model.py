"""元の絵を「そのまま」土台にして、動くモデル（.iki）を作る。

方針:
  - 土台は元の絵 1 枚。通常状態は元の絵と同じ見た目になる（パーツに切り刻まない）。
  - 目・口・眉は、生成した差分画像の「その部分だけ」を、土台の上に重ねる（目の開き・口の形・眉の形ごと）。
  - 頭の向き・傾き、体の揺れ、呼吸、髪の揺れは、土台の絵を丸ごと滑らかに変形して作る（球に貼った絵を回す近似）。
    重ねるパーツにも同じ変形を掛けるので、顔の中で位置がずれない。

使い方:
    python tools/build_overlay_model.py --template model/iki/model.iki --out model/iki/overlay.iki
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[1]
K = 2  # 作業キャンバスは基準（1 倍）の 2 倍

# ---- 差し替える範囲（1 倍座標）-----------------------------------------------
# 楕円: 中心, 半径, 上端の線（眉にかからないため。無ければ None）
AREAS = {
    "eyeL": dict(kind="ellipse", c=(497.5, 325.5), r=(43.0, 19.5), top=((458, 304.0), (530, 305.5)), feather=3.0),
    "eyeR": dict(kind="ellipse", c=(630.0, 319.0), r=(49.0, 20.0), top=((588, 301.5), (650, 290.5)), feather=3.0),
    "mouth": dict(kind="ellipse", c=(567.5, 418.0), r=(46.0, 27.0), top=None, feather=3.5),
    "owlEyes": dict(kind="ellipse", c=(330.0, 452.0), r=(52.0, 20.0), top=None, feather=3.0),
    "browL": dict(kind="rect", box=(452, 266, 552, 302), feather=2.5),
    "browR": dict(kind="rect", box=(556, 254, 662, 297), feather=2.5),
}

# 差分の名前 → 生成画像（art/gen/aligned_x2/<name>.png の name）
SOURCES = {
    "eyeL": {"75": "eye75", "50": "eye50", "25": "eye25", "closed": "eyecliosed", "smileclosed": "eyewidesmileyclosed",
             "wide": "eyewideopen", "smile": "eyejentlesmilimg"},
    "mouth": {"smile": "mouthsmile", "frown": "mouthflown", "small": "mouthopensmall", "a": "moutha", "i": "mouthi",
              "u": "mouthu", "e": "mouthe", "o": "mouthoh", "big": "mouthbigopen"},
    "owlEyes": {"closed": "owleyes"},
    "browL": {"up": "browup", "troubled": "browtroubledpng", "angry": "exangry"},
}
SOURCES["eyeR"] = SOURCES["eyeL"]
SOURCES["browR"] = SOURCES["browL"]

# 重ねる順番（あとのものが上）。目は開いている→閉じている の順に積む
ORDER = {
    "eyeL": ["wide", "smile", "75", "50", "25", "closed", "smileclosed"],
    "mouth": ["smile", "frown", "small", "u", "e", "i", "a", "o", "big"],
    "owlEyes": ["closed"],
    "browL": ["up", "troubled", "angry"],
}
ORDER["eyeR"] = ORDER["eyeL"]
ORDER["browR"] = ORDER["browL"]

# ---- 頭の動きのモデル（作業キャンバス = 2 倍の画素座標）-------------------------
HEAD_C = np.array([1132.0, 690.0])  # 頭を球とみなしたときの中心（鼻の高さ）
HEAD_R = 330.0  # 球の半径
NECK = np.array([1135.0, 1000.0])  # 首の付け根（首をかしげる軸）
ROLL_PIVOT = np.array([1135.0, 1050.0])
HEAD_W = dict(center=(1150.0, 600.0), radii=(520.0, 640.0), fall=0.35)
TRANSLATE_GAIN = 0.18  # 頭全体が向きの方向へ少しずれる割合
HAIR_Y0, HAIR_Y1 = 820.0, 2400.0  # 長い髪が揺れる範囲


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def head_weight(x, y):
    cx, cy = HEAD_W["center"]
    rx, ry = HEAD_W["radii"]
    rho = np.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)
    w = 1.0 - smoothstep(1.0, 1.0 + HEAD_W["fall"], rho)
    wy = 1.0 - smoothstep(820.0, 1150.0, y)  # あごより下は動かさない（首・肩・服）
    wy = np.maximum(wy, 0.0)
    # 長い髪・イヤリングは頭と一緒に少し動く。下へ行くほど弱く、1150 でゼロ
    # フクロウ（左肩）は動かさない
    owl = 1.0 - (1.0 - smoothstep(700.0, 900.0, x)) * smoothstep(740.0, 800.0, y)
    return w * wy * owl


def upper_weight(y):
    """体の揺れの重み: 胸（y>=1500）は 0、頭の上（y<=400）は 1。"""
    return np.clip((1500.0 - y) / 1100.0, 0.0, 1.0)


def hair_mask_fn(hair_alpha: np.ndarray):
    h, w = hair_alpha.shape

    def f(x, y):
        xi = np.clip(np.round(x).astype(int), 0, w - 1)
        yi = np.clip(np.round(y).astype(int), 0, h - 1)
        return hair_alpha[yi, xi]

    return f


def displacement(x, y, param: str, value: float, hair_fn=None):
    """(x, y) は作業キャンバスの画素座標（y は下向き）。戻り値は (dx, dy) 画素（y は下向き）。"""
    x = np.asarray(x, np.float64)
    y = np.asarray(y, np.float64)
    zero = np.zeros_like(x)
    if param == "ParamAngleX":
        th = np.radians(value)
        w = head_weight(x, y)
        u = (x - HEAD_C[0]) / HEAD_R
        v = (y - HEAD_C[1]) / HEAD_R
        z = np.sqrt(np.clip(1.0 - u * u - v * v, 0.0, 1.0))
        dx = HEAD_R * (z * np.sin(th) + u * (np.cos(th) - 1.0)) + TRANSLATE_GAIN * HEAD_R * np.sin(th)
        return dx * w, zero
    if param == "ParamAngleY":
        ph = np.radians(value)  # 正 = 上を向く（特徴が上へ動く）
        w = head_weight(x, y)
        u = (x - HEAD_C[0]) / HEAD_R
        v = (y - HEAD_C[1]) / HEAD_R
        z = np.sqrt(np.clip(1.0 - u * u - v * v, 0.0, 1.0))
        dy = -HEAD_R * (z * np.sin(ph) + v * (np.cos(ph) - 1.0)) - TRANSLATE_GAIN * HEAD_R * np.sin(ph)
        return zero, dy * w
    if param == "ParamAngleZ":
        a = np.radians(-value)  # 正 = 頭の上が右へ倒れる（時計回り）。画像座標で回すので符号を反転
        w = head_weight(x, y)
        px, py = x - ROLL_PIVOT[0], y - ROLL_PIVOT[1]
        c, s = np.cos(a), np.sin(a)
        rx, ry = px * c - py * s, px * s + py * c
        return (rx - px) * w, (ry - py) * w
    if param == "ParamBodyAngleX":
        return value * 3.0 * upper_weight(y), zero
    if param == "ParamBodyAngleY":
        return zero, -value * 2.0 * upper_weight(y)
    if param == "ParamBodyAngleZ":
        a = np.radians(-value * 0.5)
        wu = upper_weight(y)
        px, py = x - 1135.0, y - 1500.0
        c, s = np.cos(a), np.sin(a)
        rx, ry = px * c - py * s, px * s + py * c
        return (rx - px) * wu, (ry - py) * wu
    if param == "ParamBreath":
        return zero, -5.0 * value * np.clip((2300.0 - y) / 1400.0, 0.0, 1.0)
    if param in ("ParamHairSwayX", "ParamHairSwayZ") and hair_fn is not None:
        m = hair_fn(x, y) * smoothstep(HAIR_Y0, 1300.0, y) * (1.0 - smoothstep(2100.0, HAIR_Y1, y))
        k = 1.6 if param == "ParamHairSwayX" else 1.0
        # 先（下）ほど大きく揺れる
        amp = value * k * (0.3 + 1.2 * np.clip((y - HAIR_Y0) / 900.0, 0.0, 1.0))
        return amp * m, zero
    return zero, zero


# 動かすパラメータと、キーフォームの値
KEYFORMS = {
    "ParamAngleX": [-30, -20, -10, 0, 10, 20, 30],
    "ParamAngleY": [-30, -15, 0, 15, 30],
    "ParamAngleZ": [-30, -15, 0, 15, 30],
    "ParamBodyAngleX": [-10, 0, 10],
    "ParamBodyAngleY": [-10, 0, 10],
    "ParamBodyAngleZ": [-10, 0, 10],
    "ParamBreath": [0, 1],
    "ParamHairSwayX": [-20, 0, 20],
    "ParamHairSwayZ": [-20, 0, 20],
}
PATCH_PARAMS = ["ParamAngleX", "ParamAngleY", "ParamAngleZ", "ParamBodyAngleX", "ParamBodyAngleY", "ParamBodyAngleZ", "ParamBreath"]


def make_warps(verts_px, size, params, hair_fn):
    """verts_px: (N,2) 部品の頂点の、作業キャンバスでの画素座標（y 下向き）。size = (幅, 高さ)。"""
    warps = []
    for p in params:
        kfs = []
        for val in KEYFORMS[p]:
            dx, dy = displacement(verts_px[:, 0], verts_px[:, 1], p, val, hair_fn)
            off = np.empty(len(verts_px) * 2)
            off[0::2] = dx / size[0]
            off[1::2] = -dy / size[1]  # モデルは y が上向き
            kfs.append({"value": float(val), "offsets": [round(float(v), 5) for v in off]})
        warps.append({"parameter": p, "keyforms": kfs})
    return warps


def grid_axes(lo, hi, dense_lo, dense_hi, step_dense, step_sparse):
    pts = set([lo, hi])
    v = dense_lo
    while v < dense_hi:
        pts.add(float(v))
        v += step_dense
    pts.add(float(dense_hi))
    v = lo + step_sparse
    while v < hi:
        if v < dense_lo - step_sparse * 0.5 or v > dense_hi + step_sparse * 0.5:
            pts.add(float(v))
        v += step_sparse
    return np.array(sorted(pts))


def mesh_from_axes(xs, ys, uv_rect):
    """xs, ys: 部品の左上を 0 とした画素座標の格子線。戻り値: (頂点 unit, uv, indices, 頂点の画素座標)"""
    W, H = xs[-1], ys[-1]
    verts, uvs, px = [], [], []
    for y in ys:
        for x in xs:
            fx, fy = x / W, y / H
            verts += [round(fx - 0.5, 6), round(0.5 - fy, 6)]
            uvs += [uv_rect[0] + fx * uv_rect[2], uv_rect[1] + fy * uv_rect[3]]
            px.append((x, y))
    nx = len(xs)
    idx = []
    for j in range(len(ys) - 1):
        for i in range(nx - 1):
            a = j * nx + i
            b, c, d = a + 1, a + nx, a + nx + 1
            idx += [c, d, a, a, d, b]
    return verts, uvs, idx, np.array(px, np.float64)


# ---- 差分の切り出し --------------------------------------------------------------
def area_mask(shape, name):
    h, w = shape[:2]
    a = AREAS[name]
    m = np.zeros((h, w), np.float32)
    if a["kind"] == "ellipse":
        (cx, cy), (rx, ry) = a["c"], a["r"]
        cv2.ellipse(m, (round(cx * K), round(cy * K)), (round(rx * K), round(ry * K)), 0, 0, 360, 1.0, -1)
        if a["top"]:
            (x0, y0), (x1, y1) = a["top"]
            xs = np.arange(w)[None, :] / K
            line = y0 + (xs - x0) * (y1 - y0) / (x1 - x0)
            m[(np.arange(h)[:, None] / K) < line] = 0
    else:
        x0, y0, x1, y1 = (int(v * K) for v in a["box"])
        m[y0:y1, x0:x1] = 1.0
    return cv2.GaussianBlur(m, (0, 0), a["feather"] * K / 2)


def refine_shift(base_rgb, gen_rgb, core):
    """土台と生成画像の、局所的な位置ずれ（平行移動）を、範囲のまわりの輪から求める。"""
    ring = cv2.dilate(core.astype(np.uint8), np.ones((81, 81), np.uint8)) & ~cv2.dilate(core.astype(np.uint8), np.ones((9, 9), np.uint8))
    ys, xs = np.nonzero(cv2.dilate(core.astype(np.uint8), np.ones((101, 101), np.uint8)))
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    a = cv2.cvtColor(base_rgb[y0:y1, x0:x1], cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    b = cv2.cvtColor(gen_rgb[y0:y1, x0:x1], cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    mask = ring[y0:y1, x0:x1].astype(np.uint8) * 255
    M = np.eye(2, 3, dtype=np.float32)
    try:
        _, M = cv2.findTransformECC(a, b, M, cv2.MOTION_TRANSLATION, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 60, 1e-5), mask, 5)
    except cv2.error:
        return np.eye(2, 3, dtype=np.float32)
    if np.hypot(M[0, 2], M[1, 2]) > 6:  # 大きすぎるずれは信用しない
        return np.eye(2, 3, dtype=np.float32)
    return M


def ring_color_match(gen_rgb, base_rgb, ring):
    out = gen_rgb.astype(np.float32).copy()
    if ring.sum() < 200:
        return gen_rgb
    for c in range(3):
        s, r = out[..., c][ring], base_rgb[..., c][ring].astype(np.float32)
        a = float(np.clip(r.std() / max(s.std(), 1e-3), 0.9, 1.1))
        out[..., c] = out[..., c] * a + (r.mean() - a * s.mean())
    return np.clip(out, 0, 255).astype(np.uint8)


def pack(crops, max_w=2048, pad=2):
    crops = sorted(crops, key=lambda c: -c[1].height)
    x = y = shelf = width = 0
    pos = {}
    for name, im in crops:
        w, h = im.size
        if x + w + pad > max_w:
            x, y, shelf = 0, y + shelf + pad, 0
        pos[name] = (x, y, w, h)
        x += w + pad
        shelf = max(shelf, h)
        width = max(width, x)
    atlas = Image.new("RGBA", (width, y + shelf), (0, 0, 0, 0))
    for name, im in crops:
        atlas.paste(im, pos[name][:2])
    return atlas, pos


def png_uri(im: Image.Image) -> str:
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--work", type=Path, default=ROOT / "art/work/upper_x2.png")
    ap.add_argument("--gen", type=Path, default=ROOT / "art/gen/aligned_x2")
    ap.add_argument("--template", type=Path, default=ROOT / "model/iki/model.iki")
    ap.add_argument("--out", type=Path, default=ROOT / "model/iki/overlay.iki")
    ap.add_argument("--debug", type=Path, help="切り出したパッチを書き出すフォルダ")
    args = ap.parse_args(argv)

    work = np.array(Image.open(args.work).convert("RGBA"))
    H, W = work.shape[:2]
    base_rgb = work[..., :3]
    template = json.loads(args.template.read_text())

    # 長い髪の揺れの重み: 銀色の髪の画素
    hsv = cv2.cvtColor(base_rgb, cv2.COLOR_RGB2HSV)
    silver = ((hsv[..., 1] < 60) & (hsv[..., 2] > 120)).astype(np.float32) * (work[..., 3] > 128)
    hair_alpha = cv2.GaussianBlur(silver, (0, 0), 6)
    hair_fn = hair_mask_fn(hair_alpha)

    # ---- パッチを切り出す -------------------------------------------------------
    patches = []  # dict(name, area, state, order, bbox, rgba)
    ref_cache = {}
    for area, states in SOURCES.items():
        m = area_mask(work.shape, area)
        core = m > 0.5
        ys, xs = np.nonzero(m > 0.02)
        x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        ring = cv2.dilate(core.astype(np.uint8), np.ones((61, 61), np.uint8)).astype(bool) & ~cv2.dilate(core.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
        ring &= work[..., 3] > 200
        for state, src in states.items():
            f = args.gen / f"{src}.png"
            if not f.exists():
                print(f"[なし] {area}/{state} ({src})")
                continue
            if f not in ref_cache:
                ref_cache[f] = np.array(Image.open(f).convert("RGB"))
            g = ref_cache[f]
            M = refine_shift(base_rgb, g, core)
            g2 = cv2.warpAffine(g, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            d0 = np.abs(g.astype(np.float32) - base_rgb)[ring].mean()
            d1 = np.abs(g2.astype(np.float32) - base_rgb)[ring].mean()
            if d1 >= d0:  # 輪の差が減らないなら、位置合わせの補正は使わない
                M, g2, d1 = np.eye(2, 3, dtype=np.float32), g, d0
            g3 = ring_color_match(g2, base_rgb, ring)
            d2 = np.abs(g3.astype(np.float32) - base_rgb)[ring].mean()
            rgba = np.dstack([g3, (m * 255 + 0.5).astype(np.uint8)])[y0:y1, x0:x1]
            patches.append(dict(name=f"gp_{area}_{state}", area=area, state=state, bbox=(x0, y0, x1, y1), rgba=rgba))
            print(f"{area}/{state}: ずれ ({M[0,2]:+.1f},{M[1,2]:+.1f})px, 輪の差 {d0:.1f} → {d1:.1f} → {d2:.1f}")
    if args.debug:
        args.debug.mkdir(parents=True, exist_ok=True)
        for p in patches:
            Image.fromarray(p["rgba"]).save(args.debug / f"{p['name']}.png")

    # ---- テクスチャ ---------------------------------------------------------------
    atlas, pos = pack([(p["name"], Image.fromarray(p["rgba"])) for p in patches])
    AW, AH = atlas.size
    textures = [{"source": png_uri(Image.fromarray(work))}, {"source": png_uri(atlas)}]

    # ---- パーツ -------------------------------------------------------------------
    parts = []
    # 土台: 全面。頭のまわりだけ細かい格子にする
    xs = grid_axes(0, W, 400, 1900, 32, 256)
    ys = grid_axes(0, H, 0, 1250, 32, 256)
    verts, uvs, idx, vpx = mesh_from_axes(xs, ys, (0.0, 0.0, 1.0, 1.0))
    base_params = list(KEYFORMS.keys())
    parts.append({
        "id": "base", "color": [1, 1, 1, 1], "width": float(W), "height": float(H),
        "transform": {"x": 0.0, "y": 0.0}, "order": 0,
        "texture": {"index": 0, "uv": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}},
        "mesh": {"vertices": verts, "uvs": uvs, "indices": idx},
        "warps": make_warps(vpx, (W, H), base_params, hair_fn),
    })

    order_no = 1
    for area in SOURCES:
        for state in ORDER[area]:
            p = next((q for q in patches if q["area"] == area and q["state"] == state), None)
            if p is None:
                continue
            x0, y0, x1, y1 = p["bbox"]
            w, h = x1 - x0, y1 - y0
            px, py, aw, ah = pos[p["name"]]
            cell = 36
            xs_p = np.unique(np.append(np.arange(0, w, cell), w)).astype(float)
            ys_p = np.unique(np.append(np.arange(0, h, cell), h)).astype(float)
            uv = (px / AW, py / AH, aw / AW, ah / AH)
            v, u, i, vpx_p = mesh_from_axes(xs_p, ys_p, uv)
            vpx_abs = vpx_p + np.array([x0, y0])
            pid = f"ParamGP_{area}_{state}"
            parts.append({
                "id": p["name"], "color": [1, 1, 1, 1], "width": float(w), "height": float(h),
                "transform": {"x": float((x0 + x1) / 2 - W / 2), "y": float(H / 2 - (y0 + y1) / 2)},
                "order": order_no,
                "bindings": [{"parameter": pid, "channel": "opacity", "from": 0, "to": 1}],
                "texture": {"index": 1, "uv": {"x": uv[0], "y": uv[1], "width": uv[2], "height": uv[3]}},
                "mesh": {"vertices": v, "uvs": u, "indices": i},
                "warps": make_warps(vpx_abs, (w, h), PATCH_PARAMS, hair_fn),
            })
            order_no += 1

    # ---- パラメータ・表情・動き --------------------------------------------------
    std = [p for p in template["parameters"] if not p["id"].startswith("ParamGP_")]
    gp_ids = []
    for area in SOURCES:
        for state in ORDER[area]:
            gp_ids.append(f"ParamGP_{area}_{state}")
    params = std + [{"id": g, "min": 0, "max": 1, "default": 0} for g in gp_ids]

    model = {
        "version": template["version"], "name": "overlay", "canvas": {"width": W, "height": H},
        "parameters": params, "textures": textures, "parts": parts, "deformers": [],
        "physics": template["physics"], "expressions": template["expressions"], "motions": template["motions"],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(model, separators=(",", ":")))
    print(f"{args.out}: {args.out.stat().st_size / 1e6:.1f} MB, パーツ {len(parts)}, 土台の頂点 {len(vpx)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
