"""Procedurally drawn parts: things an illustrator would *draw in* because the source image has no pixels for them
(closed eyes, open mouth interiors). Rendered with 4x supersampling for clean antialiased edges."""
import numpy as np
import cv2

SS = 4


def _canvas(shape):
    h, w = shape
    return np.zeros((h * SS, w * SS), np.uint8)


def _down(mask):
    h, w = mask.shape[0] // SS, mask.shape[1] // SS
    return cv2.resize(mask, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255


def _spline(pts, n=80):
    pts = np.array(pts, np.float32)
    t = np.linspace(0, 1, len(pts))
    tt = np.linspace(0, 1, n)
    # Catmull-Rom-ish via cubic interpolation per axis
    from scipy.interpolate import CubicSpline
    cs = CubicSpline(t, pts, bc_type="natural")
    return cs(tt)


def stroke(shape, pts, width, taper=(0.35, 0.9), power=0.8):
    """Variable-width stroke along a smooth curve. width = max width px. taper = (start, end) width fraction."""
    m = _canvas(shape)
    P = _spline(pts) * SS
    n = len(P)
    for i, (x, y) in enumerate(P):
        t = i / (n - 1)
        # thicker toward the middle/end, thin at the start
        prof = np.sin(np.pi * t) ** power
        w = width * (taper[0] * (1 - t) + taper[1] * t) * (0.25 + 0.75 * prof)
        cv2.circle(m, (int(round(x)), int(round(y))), max(1, int(round(w * SS / 2))), 255, -1, cv2.LINE_AA)
    return _down(m)


def closed_eye(shape, spec):
    a = stroke(shape, spec["pts"], spec.get("width", 4.5), tuple(spec.get("taper", (0.45, 1.0))))
    col = np.array(spec.get("color", [52, 36, 56]), np.float32)
    rgb = np.ones(shape + (3,), np.float32) * col
    return rgb, a


def open_mouth(shape, spec):
    cx, cy = spec["center"]
    rx, ry = spec.get("rx", 17), spec.get("ry", 13)
    out_c = np.array(spec.get("outline", [128, 66, 72]), np.float32)
    in_c = np.array(spec.get("inner", [92, 34, 50]), np.float32)
    tg_c = np.array(spec.get("tongue", [214, 104, 112]), np.float32)
    # D-shaped mouth: flat-ish top lip, round bottom
    t = np.linspace(0, 2 * np.pi, 200, endpoint=False)
    x = rx * np.cos(t)
    y = np.where(np.sin(t) > 0, ry * np.sin(t), 0.45 * ry * np.sin(t))
    poly = (np.stack([cx + x, cy + y], 1) * SS).astype(np.int32)
    m_all = _canvas(shape); cv2.fillPoly(m_all, [poly], 255, cv2.LINE_AA)
    inner = _canvas(shape)
    poly_i = (np.stack([cx + x * 0.86, cy + y * 0.8 + 0.2 * ry], 1) * SS).astype(np.int32)
    cv2.fillPoly(inner, [poly_i], 255, cv2.LINE_AA)
    tongue = _canvas(shape)
    cv2.ellipse(tongue, (int(cx * SS), int((cy + 0.62 * ry) * SS)), (int(rx * 0.55 * SS), int(ry * 0.38 * SS)), 0, 0, 360, 255, -1, cv2.LINE_AA)
    A, I, T = _down(m_all), _down(inner), _down(tongue)
    T = np.minimum(T, I)
    rgb = out_c * (1 - I[..., None]) + in_c * I[..., None]
    rgb = rgb * (1 - T[..., None]) + tg_c * T[..., None]
    return rgb, A


def eyelid(shape, spec, rgb):
    """Skin sheet that fills the eye opening when the lid comes down. Colours are sampled from the source art just
    above and just below the opening (skin-like pixels only) and blended top->bottom."""
    import cv2 as _cv
    poly = np.array(spec["poly"], np.float32)
    m = _canvas(shape)
    _cv.fillPoly(m, [(poly * SS).astype(np.int32)], 255, _cv.LINE_AA)
    A = _down(m)
    k = float(spec.get("feather", 1.0))
    if k > 0:
        A = _cv.GaussianBlur(A, (0, 0), k)
    ys, xs = np.where(A > 0.5)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    lab = _cv.cvtColor(rgb.astype(np.uint8), _cv.COLOR_RGB2LAB).astype(np.float32)
    ref = _cv.cvtColor(np.array([[[250, 230, 221]]], np.uint8), _cv.COLOR_RGB2LAB).astype(np.float32)[0, 0]
    skin = np.linalg.norm(lab - ref, axis=2) < float(spec.get("skin_tol", 32))

    def band(b0, b1):
        sl = (slice(int(b0), int(b1)), slice(int(x0), int(x1)))
        px = rgb[sl][skin[sl]]
        return np.median(px, axis=0) if len(px) > 20 else np.array([245, 222, 212], np.float32)
    top = band(*spec["top"])
    bot = band(*spec["bottom"])
    yy = np.arange(shape[0], dtype=np.float32)[:, None]
    t = np.clip((yy - y0) / max(y1 - y0, 1), 0, 1)[..., None]
    col = top * (1 - t) + bot * t
    return np.broadcast_to(col, shape + (3,)).copy(), A


def open_mouth_line(shape, spec, rgb):
    """Mouth opening hung from the artist's own lip line. The line (found in the source) stays as the upper lip;
    the opening is drawn below it at FULL openness, the runtime scales it vertically from the line (pivot) for MouthOpen.
    Colours are taken from the line itself so it matches the art."""
    import cv2 as _cv
    x0, y0, x1, y1 = spec["box"]                   # search box around the lip line
    lum = rgb[y0:y1, x0:x1].astype(np.float32).mean(2)
    dark = lum < float(spec.get("line_thr", 190))
    cols = np.where(dark.sum(0) > 0)[0]
    xs, ys = [], []
    for c in cols:
        r = np.where(dark[:, c])[0]
        w = np.clip(float(spec.get("line_thr", 190)) - lum[r, c], 1e-3, None)
        ys.append(float((r * w).sum() / w.sum()) + y0 + 0.5); xs.append(c + x0 + 0.5)
    xs, ys = np.array(xs), np.array(ys)
    ys = np.convolve(np.pad(ys, 3, mode="edge"), np.ones(7) / 7, mode="valid")        # smooth
    lx0, lx1 = xs.min(), xs.max()
    cx = float(spec.get("cx", (lx0 + lx1) / 2)); half = float(spec.get("width", 40)) / 2
    h = float(spec.get("height", 20))
    line_col = np.array(rgb[int(np.median(ys)), int(xs[len(xs) // 2])], np.float32)
    px = np.linspace(cx - half, cx + half, 60)
    top = np.interp(px, xs, ys) + float(spec.get("gap", 1.4))
    t = (px - cx) / half
    bot = top + h * np.clip(1 - np.abs(t) ** float(spec.get("pow", 2.2)), 0, 1) ** float(spec.get("curve", 0.75))
    poly = np.concatenate([np.stack([px, top], 1), np.stack([px[::-1], bot[::-1]], 1)])
    big = _canvas(shape)
    _cv.fillPoly(big, [(poly * SS).astype(np.int32)], 255, _cv.LINE_AA)
    A = _down(big)
    outline = np.array(spec.get("outline", [112, 58, 64]), np.float32)
    inner_top = np.array(spec.get("inner", [92, 38, 50]), np.float32)
    inner_bot = np.array(spec.get("inner_low", [138, 66, 78]), np.float32)
    tongue = np.array(spec.get("tongue", [226, 118, 124]), np.float32)
    yy = np.arange(shape[0], dtype=np.float32)[:, None]
    ytop = float(top.min()); ybot = float(bot.max())
    g = np.clip((yy - ytop) / max(ybot - ytop, 1), 0, 1)[..., None]
    col = inner_top * (1 - g) + inner_bot * g
    col = np.broadcast_to(col, shape + (3,)).copy()
    # tongue: low, centred
    tg = _canvas(shape)
    _cv.ellipse(tg, (int(cx * SS), int((ytop + 0.78 * (ybot - ytop)) * SS)), (int(half * 0.62 * SS), int(0.3 * (ybot - ytop) * SS)), 0, 0, 360, 255, -1, _cv.LINE_AA)
    T = np.minimum(_down(tg), A)[..., None]
    col = col * (1 - T) + tongue * T
    # outline along the lower edge (inside the shape, ~1.4px)
    er = _cv.erode(A, _cv.getStructuringElement(_cv.MORPH_ELLIPSE, (3, 3)))
    ring = np.clip(A - er, 0, 1)[..., None]
    ring = ring * (yy > ytop + 2.5)[..., None]
    col = col * (1 - ring) + outline * ring
    return col, A, dict(pivot_y=float(np.median(ys)), cx=cx, top=ytop, bottom=ybot)


def ref_patch(shape, spec, rgb, proj_dir):
    """Pixels taken from a reference drawing that is the same art with only some area redrawn (e.g. closed eyes).
    The patch is where the reference differs from the source inside `box` (grown + feathered), so everything else
    stays the artist's original pixels."""
    import os, cv2 as _cv
    ref = _cv.imread(os.path.join(proj_dir, spec["ref"]), _cv.IMREAD_UNCHANGED)[..., :3][..., ::-1].astype(np.float32)
    src = rgb.astype(np.float32)
    if "union_refs" in spec:
        # one shared mask for every keyframe of this eye: wherever ANY keyframe differs from the source
        def load(path):
            return _cv.GaussianBlur(_cv.imread(os.path.join(proj_dir, path), _cv.IMREAD_UNCHANGED)[..., :3][..., ::-1].astype(np.float32), (0, 0), 1.0)
        base_img = src
        if "base" in spec:           # the keyframes were drawn on a different render of the art: diff against that one
            base_img = _cv.imread(os.path.join(proj_dir, spec["base"]), _cv.IMREAD_UNCHANGED)[..., :3][..., ::-1].astype(np.float32)
        base = _cv.GaussianBlur(base_img, (0, 0), 1.0)
        d = np.max([np.abs(load(r) - base).sum(2) for r in spec["union_refs"]], axis=0)
        x0, y0, x1, y1 = spec["box"]
        m = np.zeros(shape, bool)
        m[y0:y1, x0:x1] = d[y0:y1, x0:x1] > float(spec.get("thr", 70))
        m = _cv.morphologyEx(m.astype(np.uint8), _cv.MORPH_CLOSE, np.ones((5, 5), np.uint8)) > 0
        m = ndi_fill(m)
        lab_, n = _ndi().label(m)                       # keep the biggest blob(s) only
        if n:
            sz = _ndi().sum(m, lab_, range(1, n + 1))
            m = np.isin(lab_, 1 + np.flatnonzero(sz >= 0.2 * sz.max()))
        g = int(spec.get("grow", 3))
        if g:
            m = _cv.dilate(m.astype(np.uint8), _cv.getStructuringElement(_cv.MORPH_ELLIPSE, (2 * g + 1, 2 * g + 1))) > 0
        box = np.zeros(shape, bool); box[y0:y1, x0:x1] = True
        A = _cv.GaussianBlur((m & box).astype(np.float32), (0, 0), float(spec.get("feather", 1.6)))
        return ref, np.where(box, A, 0)
    if "poly" in spec:
        m = _canvas(shape)
        _cv.fillPoly(m, [(np.array(spec["poly"], np.float32) * SS).astype(np.int32)], 255, _cv.LINE_AA)
        A = _cv.GaussianBlur(_down(m), (0, 0), float(spec.get("feather", 2.0)))
        return ref, A
    x0, y0, x1, y1 = spec["box"]
    diff = np.abs(ref - src).sum(2)
    m = np.zeros(shape, bool)
    m[y0:y1, x0:x1] = diff[y0:y1, x0:x1] > float(spec.get("thr", 40))
    m = _cv.morphologyEx(m.astype(np.uint8), _cv.MORPH_CLOSE, np.ones((5, 5), np.uint8)) > 0
    m = ndi_fill(m)
    g = int(spec.get("grow", 5))
    if g:
        m = _cv.dilate(m.astype(np.uint8), _cv.getStructuringElement(_cv.MORPH_ELLIPSE, (2 * g + 1, 2 * g + 1))) > 0
    box = np.zeros(shape, bool); box[y0:y1, x0:x1] = True
    A = _cv.GaussianBlur((m & box).astype(np.float32), (0, 0), float(spec.get("feather", 2.0)))
    A = np.where(box, A, 0)
    return ref, A


def _ndi():
    from scipy import ndimage as ndi
    return ndi


def ndi_fill(m):
    from scipy import ndimage as ndi
    return ndi.binary_fill_holes(m)


RENDERERS = {"closed_eye": closed_eye, "open_mouth": open_mouth}


def render(spec, shape, rgb=None, proj_dir=None):
    s = spec["synthetic"]
    if s["type"] == "open_mouth_line":
        return open_mouth_line(shape, s, rgb)[:2]
    if s["type"] == "ref_patch":
        return ref_patch(shape, s, rgb, proj_dir)
    if s["type"] == "eyelid":
        return eyelid(shape, s, rgb)
    return RENDERERS[s["type"]](shape, s)
