"""B-2: 自動リグ済みの .iki に、生成した差分の「差し替え用パーツ」を追加する。

- パーツごとに、表示の強さを決めるパラメータ ParamGP_<範囲>_<状態>（0..1、既定 0）を追加する
- 差し替え中に元の目・口を隠すパラメータ ParamGP_<範囲>_hide（0..1）を追加し、元のパーツの不透明度に結び付ける
- どの状態をどれだけ出すかは、アプリ側（app/src/patches.js）が目の開き・口の開きなどから決める

使い方:
    python tools/add_gen_patches.py model/iki/upper_s.iki art/parts/upper_s model/iki/upper_gp.iki
（パッチの PNG は、リグに使ったレイヤーと同じ大きさ・同じ縮尺であること）
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

# 範囲 → (ぶら下げる変形, 前後関係の基準パーツ, 元のパーツで隠すもの)
AREAS = {
    "eyeL": ("eyeWarp_L", "lash_L", ["eye_L", "iris_L", "lash_L"]),
    "eyeR": ("eyeWarp_R", "lash_R", ["eye_R", "iris_R", "lash_R"]),
    "mouth": ("mouthWarp", "mouth_open", ["mouth", "mouth_open"]),
    "owlEyes": ("bodyWarp", "body", []),
}
PAD = 2


def grid_mesh(uv: dict, nx: int = 6, ny: int = 4) -> dict:
    """ワープ変形にぶら下げるための格子メッシュ（頂点は -0.5..0.5、+y が上。UV は左上原点）。"""
    verts, uvs, idx = [], [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            fx, fy = i / nx, j / ny
            verts += [round(fx - 0.5, 5), round(0.5 - fy, 5)]
            uvs += [uv["x"] + fx * uv["width"], uv["y"] + fy * uv["height"]]
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            b, c, d = a + 1, a + nx + 1, a + nx + 2
            idx += [c, d, a, a, d, b]
    return {"vertices": verts, "uvs": uvs, "indices": idx}


def pack(crops: list[tuple[str, Image.Image]], max_w: int = 2048):
    """棚詰めでアトラスを作る。戻り値: (アトラス画像, {名前: (x, y, w, h)})"""
    crops = sorted(crops, key=lambda c: -c[1].height)
    x = y = shelf = 0
    pos = {}
    width = 0
    for name, im in crops:
        w, h = im.size
        if x + w + PAD > max_w:
            x, y, shelf = 0, y + shelf + PAD, 0
        pos[name] = (x, y, w, h)
        x += w + PAD
        shelf = max(shelf, h)
        width = max(width, x)
    height = y + shelf
    atlas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for name, im in crops:
        px, py, _, _ = pos[name]
        atlas.paste(im, (px, py))
    return atlas, pos


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("model", type=Path)
    ap.add_argument("layers", type=Path)
    ap.add_argument("out", type=Path)
    args = ap.parse_args(argv)

    model = json.loads(args.model.read_text())
    Wm, Hm = model["canvas"]["width"], model["canvas"]["height"]
    files = sorted(args.layers.glob("gp_*.png"))
    if not files:
        print("パッチがありません")
        return 1

    crops, info = [], {}
    for f in files:
        m = re.match(r"gp_([A-Za-z]+)_(\w+)$", f.stem)
        if not m or m.group(1) not in AREAS:
            continue
        im = Image.open(f).convert("RGBA")
        if im.size != (Wm, Hm):
            raise SystemExit(f"{f.name}: 大きさ {im.size} がモデルのキャンバス {Wm}x{Hm} と違います")
        bbox = im.getchannel("A").point(lambda a: 255 if a > 2 else 0).getbbox()
        if not bbox:
            continue
        name = f.stem
        crops.append((name, im.crop(bbox)))
        info[name] = {"area": m.group(1), "state": m.group(2), "bbox": bbox}

    atlas, pos = pack(crops)
    buf = io.BytesIO()
    atlas.save(buf, "PNG", optimize=True)
    tex_index = len(model["textures"])
    model["textures"].append({"source": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()})
    AW, AH = atlas.size

    # 前後関係: 既存の order を 10 倍して、間に差し込む
    parts = model["parts"]
    for p in parts:
        p["order"] = p["order"] * 10
    by_id = {p["id"]: p for p in parts}
    params = {p["id"] for p in model["parameters"]}

    def add_param(pid):
        if pid not in params:
            model["parameters"].append({"id": pid, "min": 0, "max": 1, "default": 0})
            params.add(pid)

    added_areas = set()
    for k, (name, im) in enumerate(sorted(crops, key=lambda c: c[0])):
        area, state = info[name]["area"], info[name]["state"]
        deformer, anchor, hide = AREAS[area]
        x0, y0, x1, y1 = info[name]["bbox"]
        px, py, w, h = pos[name]
        pid = f"ParamGP_{area}_{state}"
        add_param(pid)
        part = {
            "id": name,
            "color": [1, 1, 1, 1],
            "width": float(w),
            "height": float(h),
            "transform": {"x": (x0 + x1) / 2 - Wm / 2, "y": Hm / 2 - (y0 + y1) / 2},
            "order": by_id[anchor]["order"] + 1 + (k % 8) / 10,
            "bindings": [{"parameter": pid, "channel": "opacity", "from": 0, "to": 1}],
            "texture": {"index": tex_index, "uv": {"x": px / AW, "y": py / AH, "width": w / AW, "height": h / AH}},
            "deformer": deformer,
        }
        part["mesh"] = grid_mesh(part["texture"]["uv"])
        parts.append(part)
        if area not in added_areas and hide:
            hid = f"ParamGP_{area}_hide"
            add_param(hid)
            for base in hide:
                by_id[base].setdefault("bindings", []).append({"parameter": hid, "channel": "opacity", "from": 1, "to": 0})
            added_areas.add(area)

    parts.sort(key=lambda p: p["order"])
    args.out.write_text(json.dumps(model, separators=(",", ":")))
    print(f"{args.out}: パッチ {len(crops)} 個、アトラス {AW}x{AH}、パラメータ {len(model['parameters'])} 個")
    return 0


if __name__ == "__main__":
    sys.exit(main())
