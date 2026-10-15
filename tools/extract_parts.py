"""P1: 1 枚絵（上半身）から、iki の自動リグ用の「役割名付きレイヤー」を切り出す。

入力: art/work/upper_x2.png（2 倍の作業キャンバス 2288x2750、透過）
出力: art/parts/upper/<role>.png（全レイヤー同じサイズの透過 PNG）と preview.png

座標は「元の絵（1 倍, 1144x1375）」の座標で書く。K 倍して作業キャンバスに合わせる。
必要な環境変数: LAMA_WEIGHTS=big-lama.pt のパス

使い方:
    LAMA_WEIGHTS=... python tools/extract_parts.py art/work/upper_x2.png art/parts/upper
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

K = 2  # 作業キャンバスは元絵の 2 倍

# ---- 座標（1 倍）--------------------------------------------------------
FACE = [(500, 212), (560, 200), (620, 210), (660, 245), (680, 300), (692, 350), (690, 375), (676, 386),
        (655, 398), (642, 414), (622, 436), (595, 462), (572, 474), (552, 468), (528, 450), (504, 426),
        (486, 404), (470, 388), (450, 382), (440, 360), (444, 325), (455, 285), (470, 245)]
EYE_OPEN = {
    "L": [(464, 320), (472, 317), (484, 317), (500, 318), (515, 320), (526, 324), (531, 330), (522, 331),
          (510, 333), (497, 334), (484, 333), (472, 330), (466, 325)],
    "R": [(590, 322), (598, 316), (610, 312), (625, 311), (642, 310), (658, 310), (670, 313), (668, 319),
          (656, 323), (642, 326), (628, 328), (614, 328), (602, 326), (594, 324)],
}
# 眉: 中心線の両端 (x, y) と、両端の太さ（1 倍座標）。太い方が眉頭（鼻に近い側）
BROW_STROKE = {"L": ((458, 296.0), (525, 299.0), 4.6, 7.0),
               "R": ((591, 295.0), (646, 283.5), 6.6, 4.4)}
BROW_POLY = {"L": [(458, 292), (497, 292.5), (525, 295), (525, 302), (497, 301), (458, 299)],
             "R": [(590, 290), (615, 286), (644, 281), (648, 286), (616, 293), (591, 299)]}
MOUTH_BOX = (530, 403, 606, 419)
NOSE_BOX = (556, 350, 568, 392)
OWL = [(242, 392), (300, 398), (330, 402), (352, 362), (378, 376), (395, 430), (412, 470), (415, 500),
       (412, 535), (395, 560), (380, 585), (340, 598), (300, 592), (255, 580), (238, 560), (226, 540),
       (245, 500), (235, 470), (250, 440)]
# 頭まわり（髪・髪飾り・耳飾り）として hair_front に入れる範囲
HEAD_ROI = [[(250, 0), (900, 0), (900, 400), (250, 400)],
            [(680, 400), (830, 400), (830, 535), (680, 535)],
            [(425, 380), (485, 380), (485, 525), (425, 525)]]
NECK_FILL = [(498, 396), (642, 396), (645, 500), (495, 500)]  # あごの下（首）。頭を動かしたとき見える
MOUTH_CENTER = (567.5, 411.0)  # 閉じた口の中心（1 倍座標）
LOWER_FACE_Y = 395  # これより下の輪郭は、肌の色から求める


def poly_mask(shape, pts, k=K) -> np.ndarray:
    m = np.zeros(shape[:2], np.uint8)
    cv2.fillPoly(m, [(np.array(pts, np.float32) * k).round().astype(np.int32)], 1)
    return m.astype(bool)


def box_mask(shape, box, k=K) -> np.ndarray:
    x0, y0, x1, y1 = (int(v * k) for v in box)
    m = np.zeros(shape[:2], bool)
    m[y0:y1, x0:x1] = True
    return m


def dilate(m: np.ndarray, r: int) -> np.ndarray:
    return cv2.dilate(m.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))).astype(bool)


def erode(m: np.ndarray, r: int) -> np.ndarray:
    return cv2.erode(m.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))).astype(bool)


def largest_component(m: np.ndarray) -> np.ndarray:
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), connectivity=8)
    if n <= 1:
        return m
    i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return lab == i


def soft(m: np.ndarray, sigma: float = 1.2) -> np.ndarray:
    return cv2.GaussianBlur(m.astype(np.float32), (0, 0), sigma)


def layer(rgb: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    return np.dstack([rgb, np.clip(alpha * 255 + 0.5, 0, 255).astype(np.uint8)])


def hsv_of(rgb: np.ndarray):
    h = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    return h[..., 0].astype(int), h[..., 1].astype(int), h[..., 2].astype(int)


def luma(rgb: np.ndarray) -> np.ndarray:
    return rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114


def draw_mouth_open(shape, k=K, width=50.0, height=26.0) -> np.ndarray:
    """開いた口（「あ」）を、4 倍のスーパーサンプリングで描く。閉じた口の位置に重ねる。"""
    from PIL import ImageDraw

    ss = 4
    h, w = shape[:2]
    cx, cy = MOUTH_CENTER
    # 口の周りだけ描く小さいキャンバス（1 倍座標で 90x60）
    bw, bh = 90, 60
    img = Image.new("RGBA", (bw * k * ss, bh * k * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    S_ = k * ss

    def P(x, y):  # 口の中心を (bw/2, bh/2) にした 1 倍座標 → 画素
        return ((bw / 2 + x) * S_, (bh / 2 + y) * S_)

    hw = width / 2
    top, bot = -height * 0.30, height * 0.70
    outline, inner, tongue, teeth = (120, 52, 52, 255), (74, 24, 36, 255), (206, 96, 110, 255), (252, 246, 240, 255)
    # 口の形: 上は浅いアーチ、下は丸い
    pts = []
    for i in range(0, 181, 5):
        t = np.radians(i)
        pts.append(P(-hw * np.cos(t) * 1.0, top - 2.5 * np.sin(t)))  # 上唇（左→右）
    for i in range(0, 181, 5):
        t = np.radians(i)
        pts.append(P(hw * np.cos(t), top + (bot - top) * np.sin(t)))  # 下側（右→左）
    d.polygon(pts, fill=inner, outline=outline, width=max(2, int(1.2 * S_)))
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    # 舌（下側の楕円）と歯（上の帯）を、口の形で切り抜く
    layer_ = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer_)
    ld.ellipse([P(-hw * 0.62, top + (bot - top) * 0.52), P(hw * 0.62, bot + 6)], fill=tongue)
    ld.rectangle([P(-hw, top - 4), P(hw, top + (bot - top) * 0.22)], fill=teeth)
    clipped = Image.new("RGBA", img.size, (0, 0, 0, 0))
    clipped.paste(layer_, (0, 0), mask)
    img.alpha_composite(clipped)
    d = ImageDraw.Draw(img)
    d.line(pts + [pts[0]], fill=outline, width=max(3, int(1.3 * S_)), joint="curve")
    small = img.resize((bw * k, bh * k), Image.LANCZOS)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(small, (int((cx - bw / 2) * k), int((cy - bh / 2) * k)))
    return np.array(out)


class Parts:
    def __init__(self, src: Path):
        im = np.array(Image.open(src).convert("RGBA"))
        self.rgb = im[..., :3].copy()
        self.a = im[..., 3].astype(np.float32) / 255.0
        self.shape = self.rgb.shape
        self.h, self.w = self.rgb.shape[:2]
        self.opaque = self.a > 0.5
        H, S, V = hsv_of(self.rgb)
        self.H, self.S, self.V = H, S, V
        self.L = luma(self.rgb)
        self.skin = (((H <= 20) | (H >= 170)) & (S >= 18) & (S <= 110) & (V >= 170) & self.opaque)
        # 「きれいな肌」: 髪の影や陰影を含まない、平らな肌色だけ
        self.skin_clean = (((H <= 16) | (H >= 172)) & (S >= 22) & (S <= 58) & (V >= 222) & self.opaque)

    # --- 目 ---------------------------------------------------------------
    def eye(self, side: str):
        sh = self.shape
        opening = poly_mask(sh, EYE_OPEN[side])
        ys, xs = np.nonzero(opening)
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        pad = 6 * K
        roi = np.zeros_like(opening)
        roi[max(y0 - pad, 0):y1 + pad, max(x0 - pad, 0):x1 + pad] = True

        # 虹彩: 青紫で彩度が高い塊（瞳孔とハイライトは穴として埋める）
        blue = ((self.H >= 100) & (self.H <= 150) & (self.S >= 55) & (self.V >= 110)) & dilate(opening, 3 * K // 2)
        blob = largest_component(cv2.morphologyEx(blue.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)).astype(bool))
        contours, _ = cv2.findContours(blob.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        filled = np.zeros_like(blob, np.uint8)
        cv2.drawContours(filled, contours, -1, 1, -1)
        blob = filled.astype(bool)
        # 瞳孔（暗い塊）の中心を、虹彩の中心とみなす
        by, bx = np.nonzero(blob)
        dark = blob & (self.L < 70)
        if dark.sum() > 20:
            dy, dx = np.nonzero(dark)
            cx, cy = dx.mean(), dy.mean()
        else:
            cx, cy = bx.mean(), by.mean()
        r = (bx.max() - bx.min() + 1) / 2.0
        circle = np.zeros_like(blob, np.uint8)
        cv2.circle(circle, (int(round(cx)), int(round(cy))), int(round(r)), 1, -1)
        iris_full = circle.astype(bool)
        # 見えていない虹彩の上下は、見えている部分から補う
        iris_rgb = cv2.inpaint(self.rgb, (iris_full & ~blob).astype(np.uint8) * 255, 4, cv2.INPAINT_TELEA)
        iris_a = soft(iris_full, 1.0)

        # 上まつ毛・まぶたの線: 開口部の上側の暗い画素
        band = dilate(opening, 5 * K) & ~erode(opening, 1) & (np.arange(self.h)[:, None] < (y0 + y1) / 2 + 2 * K)
        lash = band & (self.L < 125) & ~blob
        lash = lash | (opening & (self.L < 90) & ~blob & (np.arange(self.h)[:, None] < y0 + (y1 - y0) * 0.45))
        lash = cv2.morphologyEx(lash.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)).astype(bool)
        lash_a = soft(lash, 0.9)

        # 白目: 開口部の全面（虹彩・まつ毛の下は、周りの白から補う）
        lid_skin = (((self.H <= 22) | (self.H >= 168)) & (self.S >= 15) & (self.S <= 140) & (self.V >= 150))
        sclera_area = (opening & ~lid_skin) | blob
        sclera_area = cv2.morphologyEx(sclera_area.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)).astype(bool)
        sclera_area = largest_component(sclera_area | lash)
        hole = (blob | lash) & dilate(sclera_area, 2)
        scl_rgb = cv2.inpaint(self.rgb, hole.astype(np.uint8) * 255, 5, cv2.INPAINT_TELEA)
        scl_a = soft(sclera_area, 1.0)
        return {
            "opening": opening, "iris_full": iris_full, "blob": blob, "lash": lash, "sclera_area": sclera_area,
            "iris": layer(iris_rgb, iris_a), "lash_layer": layer(self.rgb, lash_a),
            "sclera": layer(scl_rgb, scl_a), "center": (cx, cy), "r": r,
        }

    # --- 眉・口 -------------------------------------------------------------
    def brow(self, side: str):
        """眉は、元の絵の眉の帯に合わせた滑らかな形で描き直す（髪の線が交差していて、画素の抽出が汚くなるため）。
        色は、帯の中の暗い画素の中央値。"""
        region = poly_mask(self.shape, BROW_POLY[side])
        dark = region & (self.L < 150) & self.opaque
        color = np.median(self.rgb[dark], axis=0).astype(np.uint8)
        (xa, ya), (xb, yb), ta, tb = BROW_STROKE[side]
        ss = 4  # 滑らかな縁のためのスーパーサンプリング
        canvas = np.zeros((self.h * ss // 1, self.w * ss // 1), np.uint8)
        n = 40
        for i in range(n):
            t0, t1 = i / n, (i + 1) / n
            p0 = ((xa + (xb - xa) * t0) * K * ss, (ya + (yb - ya) * t0) * K * ss)
            p1 = ((xa + (xb - xa) * t1) * K * ss, (ya + (yb - ya) * t1) * K * ss)
            r0 = (ta + (tb - ta) * t0) / 2 * K * ss
            r1 = (ta + (tb - ta) * t1) / 2 * K * ss
            cv2.circle(canvas, (round(p0[0]), round(p0[1])), max(1, round(r0)), 255, -1)
            cv2.line(canvas, (round(p0[0]), round(p0[1])), (round(p1[0]), round(p1[1])), 255, max(1, round((r0 + r1))))
        cv2.circle(canvas, (round(xb * K * ss), round(yb * K * ss)), max(1, round(tb / 2 * K * ss)), 255, -1)
        stroke = cv2.resize(canvas, (self.w, self.h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
        return stroke, color

    def mouth(self):
        box = box_mask(self.shape, MOUTH_BOX)
        skin_ref = np.median(self.rgb[box & self.skin], axis=0)
        diff = np.abs(self.rgb.astype(np.float32) - skin_ref).sum(-1)
        m = box & (diff > 60)
        return largest_component(cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)).astype(bool))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src", type=Path)
    ap.add_argument("outdir", type=Path)
    ap.add_argument("--debug", type=Path, help="途中経過の画像を書き出すフォルダ")
    args = ap.parse_args(argv)

    from lama import inpaint

    P = Parts(args.src)
    out = args.outdir
    out.mkdir(parents=True, exist_ok=True)
    dbg = args.debug
    if dbg:
        dbg.mkdir(parents=True, exist_ok=True)

    eyes = {s: P.eye(s) for s in "LR"}
    brow_info = {s: P.brow(s) for s in "LR"}
    brows = {s: brow_info[s][0] > 0.3 for s in "LR"}  # マスクとして使うときの 2 値版
    mouth = P.mouth()
    face_poly = poly_mask(P.shape, FACE)
    nose_box = box_mask(P.shape, NOSE_BOX)
    yy = np.arange(P.h)[:, None]
    upper = yy < LOWER_FACE_Y * K

    # --- 顔の肌（目・眉・口・髪を取り除いて、肌で埋める）--------------------
    feature = np.zeros_like(face_poly)
    for s in "LR":
        e = eyes[s]
        feature |= dilate(e["sclera_area"] | e["lash"] | e["blob"], 4 * K)
        feature |= dilate(brows[s], 3 * K)
    feature |= dilate(mouth, 3 * K)
    skin_ok = erode(P.skin_clean & ~feature, 1)
    hair_on_face = face_poly & upper & ~skin_ok & ~nose_box
    lower_junk = face_poly & ~upper & ~dilate(P.skin, 2) & ~nose_box
    mask = hair_on_face | lower_junk | (face_poly & feature)
    mask = dilate(mask, 2) & dilate(face_poly, 4)
    mask[nose_box] = False
    # LaMa は顔まわりだけの切り抜きで実行する
    ys, xs = np.nonzero(dilate(face_poly, 12))
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    crop_rgb = P.rgb[y0:y1, x0:x1].copy()
    crop_mask = mask[y0:y1, x0:x1]
    # マスクの外側が顔の外（背景や髪）だと、肌の色が混ざるので、周りを肌色で塗って文脈を揃える
    skin_color = np.median(P.rgb[P.skin & face_poly], axis=0).astype(np.uint8)
    ctx = ~dilate(face_poly[y0:y1, x0:x1], 0)
    crop_rgb[ctx] = skin_color
    filled = inpaint(crop_rgb, crop_mask)
    face_rgb = P.rgb.copy()
    face_rgb[y0:y1, x0:x1] = np.where(face_poly[y0:y1, x0:x1, None], filled, face_rgb[y0:y1, x0:x1])

    # 顔の外形: 上半分は多角形、下半分（あご）は肌の色から
    jaw = dilate(P.skin & face_poly, 3) | (dilate(P.skin & face_poly, 5) & (P.L < 110))
    jaw = largest_component(cv2.morphologyEx(jaw.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)).astype(bool))
    face_alpha_mask = (face_poly & upper) | (face_poly & ~upper & jaw)
    face_alpha_mask = erode(dilate(face_alpha_mask, 2), 2)
    face_layer = layer(face_rgb, soft(face_alpha_mask, 1.0))

    def save(name, arr):
        Image.fromarray(arr, "RGBA").save(out / f"{name}.png")

    # --- 髪・髪飾り（顔の前に出る部分）と、胴体 ---------------------------------
    owl = poly_mask(P.shape, OWL)
    roi = np.zeros_like(face_poly)
    for r in HEAD_ROI:
        roi |= poly_mask(P.shape, r)
    roi &= ~owl
    hair_color = (P.L < 105) | (((P.H >= 95) & (P.H <= 175)) & (P.S >= 14)) | ((P.S < 30) & (P.V < 240) & (P.V > 60))
    used = np.zeros_like(face_poly)
    for s_ in "LR":
        used |= dilate(eyes[s_]["sclera_area"] | eyes[s_]["lash"] | eyes[s_]["blob"], 2 * K)
        used |= dilate(brows[s_], 1 * K)
    used |= dilate(mouth, 2 * K)
    face_skin_px = face_poly & ~hair_color
    hair_front_m = roi & P.opaque & ~face_skin_px & ~used
    hair_front_m = hair_front_m | (roi & P.opaque & face_poly & hair_color & ~used)
    hair_front_a = np.where(hair_front_m, P.a, 0.0)
    save("hair_front", layer(P.rgb, hair_front_a))

    face_cover = face_alpha_mask | used
    # 体: 髪の前面と重なる所は基本的に除くが、首より下に垂れる銀髪（ROI の下端をまたぐ房）は、
    # 髪を動かしたとき隙間が空かないように、体にも残す（髪飾り・耳飾りは二重にならないよう除く）。
    silver = (P.S < 45) & (P.V > 140)
    keep_dup = hair_front_m & silver & (np.arange(P.h)[:, None] >= 380 * K)
    body_m = P.opaque & ~face_cover & (~hair_front_m | keep_dup)
    # 首: あごの下から上へ、頭を動かしたとき見える部分を埋める（周りの肌と襟から補う）
    neck = poly_mask(P.shape, NECK_FILL) & ~body_m
    ys2, xs2 = np.nonzero(dilate(neck, 12))
    ny0, ny1, nx0, nx1 = ys2.min(), ys2.max() + 1, xs2.min(), xs2.max() + 1
    nb_rgb = P.rgb[ny0:ny1, nx0:nx1].copy()
    nb_known = body_m[ny0:ny1, nx0:nx1]
    nb_rgb[~nb_known] = skin_color
    neck_fill = inpaint(nb_rgb, neck[ny0:ny1, nx0:nx1])
    body_rgb = P.rgb.copy()
    body_rgb[ny0:ny1, nx0:nx1] = np.where(neck[ny0:ny1, nx0:nx1, None], neck_fill, body_rgb[ny0:ny1, nx0:nx1])
    body_a = np.where(body_m, P.a, 0.0)
    body_a = np.maximum(body_a, soft(neck, 1.0) * 1.0)
    save("body", layer(body_rgb, body_a))

    # 後ろ髪: 頭の後ろの髪のかたまり（頭を回したとき、隙間から透けないようにする）
    mass = dilate(hair_front_m | face_poly, 3 * K)
    mass = cv2.morphologyEx(mass.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8)).astype(bool)
    mass &= roi | face_poly
    mass &= (np.arange(P.h)[:, None] < 470 * K)
    small_rgb = cv2.resize(P.rgb, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
    known_small = cv2.resize((hair_front_m & ~face_poly).astype(np.uint8), None, fx=0.25, fy=0.25, interpolation=cv2.INTER_NEAREST).astype(bool)
    hole_small = cv2.resize(mass.astype(np.uint8), None, fx=0.25, fy=0.25, interpolation=cv2.INTER_NEAREST).astype(bool) & ~known_small
    small_rgb[~known_small & ~hole_small] = 0
    back_small = cv2.inpaint(small_rgb, hole_small.astype(np.uint8) * 255, 9, cv2.INPAINT_TELEA)
    back_rgb = cv2.resize(back_small, (P.w, P.h), interpolation=cv2.INTER_CUBIC)
    save("hair_back", layer(back_rgb, soft(mass, 2.0)))

    # 開いた口
    save("mouth_open", draw_mouth_open(P.shape))

    # --- 保存 ---------------------------------------------------------------
    save("face", face_layer)
    for s in "LR":
        e = eyes[s]
        save(f"eye_{s}", e["sclera"])
        save(f"iris_{s}", e["iris"])
        save(f"lash_{s}", e["lash_layer"])
        brow_rgb = np.empty_like(P.rgb)
        brow_rgb[:] = brow_info[s][1]
        save(f"brow_{s}", layer(brow_rgb, brow_info[s][0]))
    save("mouth", layer(P.rgb, soft(mouth, 0.9)))

    if dbg:
        def dump(name, m):
            Image.fromarray((m.astype(np.uint8) * 255)).save(dbg / f"{name}.png")
        dump("inpaint_mask", mask)
        dump("skin", P.skin)
        dump("face_alpha", face_alpha_mask)
        for s in "LR":
            dump(f"blob_{s}", eyes[s]["blob"])
            dump(f"lash_{s}", eyes[s]["lash"])
            dump(f"brow_{s}", brows[s])
        dump("mouth", mouth)
    print("written:", sorted(p.name for p in out.glob("*.png")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
