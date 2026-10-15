"""B-1: 生成した差分（目・口・フクロウの目）を元の絵に位置合わせし、「差し替え用パーツ」にする。

入力:  art/gen/output/ の差分画像（元の絵を ChatGPT などで編集したもの）
       art/gen/input/upper_full.png（位置合わせの基準。作業キャンバスの 1/2）
       art/work/upper_x2.png（作業キャンバス。色合わせの基準）
出力:  <outdir>/gp_<グループ>_<状態>.png（作業キャンバスと同じ大きさの透過 PNG）
       <outdir>/_gen_patches_preview.jpg（確認用）

使い方:
    python tools/build_gen_patches.py art/parts/upper
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch_detail import estimate_transform  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "art/gen/input/upper_full.png"
K = 2  # 作業キャンバスは基準の 2 倍


def ellipse_area(c, r, top=None):
    return {"c": c, "r": r, "top": top}


# 差し替える範囲（1 倍座標）。top は「この線より上は使わない」（眉にかからないように）
AREAS = {
    "eyeL": ellipse_area((497.5, 325.5), (43.0, 19.5), ((458, 304.0), (530, 305.5))),
    "eyeR": ellipse_area((630.0, 319.0), (49.0, 20.0), ((588, 301.5), (650, 290.5))),
    "mouth": ellipse_area((567.5, 418.0), (46.0, 27.0)),
    "owlEyes": ellipse_area((330.0, 452.0), (52.0, 20.0)),
}
FEATHER = {"eyeL": 3.5, "eyeR": 3.5, "mouth": 4.5, "owlEyes": 3.0}

# グループ → 状態 → ファイル名（「ルナリス」・空白・記号を除き、小文字にしたもの）の候補
GROUPS = {
    "eye": {  # eyeL と eyeR の両方に使う
        "75": ["eye75"], "50": ["eye50"], "25": ["eye25"], "closed": ["eyecliosed", "eyeclosed"],
        "smileclosed": ["eyewidesmileyclosed", "eyesmileclosed"], "wide": ["eyewideopen", "eyewide"],
        "smile": ["eyejentlesmilimg", "eyegentlesmiling", "eyesmile"],
    },
    "mouth": {
        "smile": ["mouthsmile"], "frown": ["mouthflown", "mouthfrown"], "small": ["mouthopensmall"],
        "a": ["moutha"], "i": ["mouthi"], "u": ["mouthu"], "e": ["mouthe"], "o": ["mouthoh", "moutho"],
        "big": ["mouthbigopen"],
    },
    "owlEyes": {"closed": ["owleyes", "owleyesclosed"]},
}


def norm(name: str) -> str:
    s = name.lower().replace("ルナリス", "")
    return "".join(ch for ch in s if ch.isalnum())


def find(keys, files):
    hits = [f for f in files if norm(Path(f).stem) in keys]
    return sorted(hits)[0] if hits else None


def area_mask(shape, name):
    h, w = shape[:2]
    a = AREAS[name]
    m = np.zeros((h, w), np.float32)
    (cx, cy), (rx, ry) = a["c"], a["r"]
    cv2.ellipse(m, (round(cx * K), round(cy * K)), (round(rx * K), round(ry * K)), 0, 0, 360, 1.0, -1)
    if a["top"]:
        (x0, y0), (x1, y1) = a["top"]
        xs = np.arange(w)[None, :] / K
        line = y0 + (xs - x0) * (y1 - y0) / (x1 - x0)
        m[(np.arange(h)[:, None] / K) < line] = 0
    return cv2.GaussianBlur(m, (0, 0), FEATHER[name] * K / 2)


def color_match(src, ref, sel):
    """sel の範囲で、src の色を ref に合わせる（チャンネルごとの一次式）。"""
    out = src.astype(np.float32).copy()
    if sel.sum() < 200:
        return src
    for c in range(3):
        s, r = out[..., c][sel], ref[..., c][sel].astype(np.float32)
        a = float(np.clip(r.std() / max(s.std(), 1e-3), 0.8, 1.25))
        out[..., c] = out[..., c] * a + (r.mean() - a * s.mean())
    return np.clip(out, 0, 255).astype(np.uint8)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("outdir", type=Path)
    ap.add_argument("--gen", type=Path, default=ROOT / "art/gen/output")
    ap.add_argument("--work", type=Path, default=ROOT / "art/work/upper_x2.png")
    args = ap.parse_args(argv)

    ref1 = np.array(Image.open(REF).convert("RGBA"))
    work = np.array(Image.open(args.work).convert("RGBA"))
    H, W = work.shape[:2]
    files = [f for f in glob.glob(str(args.gen / "*")) if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
    args.outdir.mkdir(parents=True, exist_ok=True)
    hsv = cv2.cvtColor(work[..., :3], cv2.COLOR_RGB2HSV)
    skin = (((hsv[..., 0] <= 16) | (hsv[..., 0] >= 172)) & (hsv[..., 1] >= 20) & (hsv[..., 1] <= 75) & (hsv[..., 2] >= 205))

    cache = {}
    aligned_dir = ROOT / "art/gen/aligned_x2"

    def warped(f):
        if f not in cache:
            pre = aligned_dir / f"{norm(Path(f).stem)}.png"
            if pre.exists():  # tools/gen_align.py で位置合わせ・鮮明化したもの
                rgb = np.array(Image.open(pre).convert("RGB"))
                cache[f] = (np.dstack([rgb, np.full(rgb.shape[:2], 255, np.uint8)]), -1.0)
            else:
                g = np.array(Image.open(f).convert("RGBA"))
                M, inl, tot, err = estimate_transform(ref1, g)
                cache[f] = (cv2.warpAffine(g, M * K, (W, H), flags=cv2.INTER_LANCZOS4, borderValue=(255, 255, 255, 255)), err)
        return cache[f]

    # 色合わせの基準: 顔の下地（face.png）があれば、それを重ねた見た目に合わせる
    plate = args.outdir / "face.png"
    if plate.exists():
        fp = np.array(Image.open(plate).convert("RGBA")).astype(np.float32)
        a = fp[..., 3:4] / 255
        work = work.copy()
        work[..., :3] = (fp[..., :3] * a + work[..., :3] * (1 - a)).astype(np.uint8)
        hsv = cv2.cvtColor(work[..., :3], cv2.COLOR_RGB2HSV)
        skin = (((hsv[..., 0] <= 16) | (hsv[..., 0] >= 172)) & (hsv[..., 1] >= 20) & (hsv[..., 1] <= 75) & (hsv[..., 2] >= 205))

    made, report = [], {}
    for group, states in GROUPS.items():
        areas = ["eyeL", "eyeR"] if group == "eye" else [group]
        for state, keys in states.items():
            f = find(keys, files)
            if not f:
                print(f"[なし] {group}/{state}")
                continue
            img, err = warped(f)
            for area in areas:
                m = area_mask(work.shape, area)
                core = m > 0.5
                ring = cv2.dilate(core.astype(np.uint8), np.ones((19, 19), np.uint8)).astype(bool) & ~core & skin
                rgb = color_match(img[..., :3], work[..., :3], ring)
                name = f"gp_{area}_{state}"
                Image.fromarray(np.dstack([rgb, (m * 255 + 0.5).astype(np.uint8)]), "RGBA").save(args.outdir / f"{name}.png")
                made.append((area, state, name))
                report[name] = {"source": Path(f).name, "align_err_px": round(err, 2)}
            print(f"[{group}/{state}] {Path(f).name} (位置合わせ誤差 {err:.2f}px)")
    (args.outdir / "_gen_patches.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))

    # 確認用の一覧: 範囲ごとに、元の絵と、各状態の差し替え
    crops = {"eyeL": (880, 580, 1140, 700), "eyeR": (1150, 565, 1420, 685), "mouth": (1030, 760, 1240, 900), "owlEyes": (520, 840, 800, 960)}
    rows = []
    for area, box in crops.items():
        tiles = [work[box[1]:box[3], box[0]:box[2], :3]]
        for a, state, name in made:
            if a != area:
                continue
            lay = np.array(Image.open(args.outdir / f"{name}.png"))
            al = lay[..., 3:4].astype(np.float32) / 255
            comp = (lay[..., :3] * al + work[..., :3] * (1 - al)).astype(np.uint8)
            tiles.append(comp[box[1]:box[3], box[0]:box[2]])
        rows.append(np.concatenate(tiles, axis=1))
    wmax = max(r.shape[1] for r in rows)
    sheet = np.concatenate([np.pad(r, ((0, 4), (0, wmax - r.shape[1]), (0, 0))) for r in rows], axis=0)
    Image.fromarray(sheet).save(args.outdir / "_gen_patches_preview.jpg", quality=90)
    return 0


if __name__ == "__main__":
    sys.exit(main())
