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
    """sel の範囲で、src の色の分布（チャンネルごとのヒストグラム）を ref に合わせる。
    生成画像は目のまわりが全体にぼんやり明るく、まつ毛や虹彩のコントラストが落ちるので、元の絵の分布に戻す。"""
    out = src.astype(np.float32).copy()
    if sel.sum() < 200:
        return src
    for c in range(3):
        s_vals = np.sort(out[..., c][sel])
        r_vals = np.sort(ref[..., c][sel].astype(np.float32))
        n = min(len(s_vals), len(r_vals))
        s_q = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(s_vals)), s_vals)
        r_q = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(r_vals)), r_vals)
        # 単調な対応表にして、全画素へ適用（0.85 の強さ）
        mapped = np.interp(out[..., c], s_q, r_q)
        out[..., c] = out[..., c] * 0.15 + mapped * 0.85
    return np.clip(out, 0, 255).astype(np.uint8)


def skin_shift(src, ref, sel_skin):
    """肌の画素だけから、src → ref の平均の差を求めて全体に足す（口の中の赤などの色は変えない）。"""
    if sel_skin.sum() < 200:
        return src
    d = ref[sel_skin].astype(np.float32).mean(0) - src[sel_skin].astype(np.float32).mean(0)
    return np.clip(src.astype(np.float32) + d, 0, 255).astype(np.uint8)


def feature_alpha(rgb, plate_rgb, lo=10.0, hi=34.0):
    """下地（肌）との違いが大きい所だけを不透明にする。目や口のまわりの肌が「四角く浮く」のを防ぐ。"""
    d = np.abs(rgb.astype(np.float32) - plate_rgb.astype(np.float32)).max(-1)
    d = cv2.GaussianBlur(d, (0, 0), 0.8)
    a = np.clip((d - lo) / (hi - lo), 0, 1)
    a = a * a * (3 - 2 * a)
    return cv2.dilate(a, np.ones((3, 3), np.uint8))


def fill_under_hair(rgb, covered):
    """前髪で隠れている画素（差し替えパーツの中に焼き込まれた髪の毛）を、周りから埋める。
    髪は別のパーツとして動くので、焼き込まれたままだと、顔を動かしたときに髪が二重に見える。"""
    if not covered.any():
        return rgb
    ys, xs = np.nonzero(cv2.dilate(covered.astype(np.uint8), np.ones((21, 21), np.uint8)))
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    crop = np.ascontiguousarray(rgb[y0:y1, x0:x1])
    out = cv2.inpaint(crop, covered[y0:y1, x0:x1].astype(np.uint8) * 255, 5, cv2.INPAINT_TELEA)
    res = rgb.copy()
    res[y0:y1, x0:x1] = out
    return res


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
    orig = work.copy()  # 色合わせの基準は、元の絵のまま（顔の下地を重ねると、目の無い肌だけになってしまう）
    plate = args.outdir / "face.png"
    if plate.exists():
        fp = np.array(Image.open(plate).convert("RGBA")).astype(np.float32)
        a = fp[..., 3:4] / 255
        work = work.copy()
        work[..., :3] = (fp[..., :3] * a + work[..., :3] * (1 - a)).astype(np.uint8)
        hsv = cv2.cvtColor(work[..., :3], cv2.COLOR_RGB2HSV)
        skin = (((hsv[..., 0] <= 16) | (hsv[..., 0] >= 172)) & (hsv[..., 1] >= 20) & (hsv[..., 1] <= 75) & (hsv[..., 2] >= 205))

    hf_path = args.outdir / "hair_front.png"
    hf_a = np.array(Image.open(hf_path).convert("RGBA"))[..., 3].astype(np.float32) / 255 if hf_path.exists() else np.zeros(work.shape[:2], np.float32)
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
                sel = cv2.dilate((m > 0.3).astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
                diff_alpha = area in ("eyeL", "eyeR", "mouth")  # 元のパーツを隠して差し替えるもの
                if area == "mouth":
                    ring = sel & ~(m > 0.6) & skin
                    rgb = skin_shift(img[..., :3], orig[..., :3], ring)
                else:
                    rgb = color_match(img[..., :3], orig[..., :3], sel)
                if diff_alpha:
                    covered = (hf_a > 0.3) & sel
                    rgb = fill_under_hair(rgb, covered)
                    a = m * feature_alpha(rgb, work[..., :3])
                else:
                    a = m
                name = f"gp_{area}_{state}"
                Image.fromarray(np.dstack([rgb, (a * 255 + 0.5).astype(np.uint8)]), "RGBA").save(args.outdir / f"{name}.png")
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
