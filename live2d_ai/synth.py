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


def ref_patch(shape, spec, rgb, proj_dir):
    """Pixels taken from a reference drawing that is the same art with only some area redrawn (e.g. closed eyes).
    The patch is where the reference differs from the source inside `box` (grown + feathered), so everything else
    stays the artist's original pixels."""
    import os, cv2 as _cv
    ref = _cv.imread(os.path.join(proj_dir, spec["ref"]), _cv.IMREAD_UNCHANGED)[..., :3][..., ::-1].astype(np.float32)
    src = rgb.astype(np.float32)
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


def ndi_fill(m):
    from scipy import ndimage as ndi
    return ndi.binary_fill_holes(m)


RENDERERS = {"closed_eye": closed_eye, "open_mouth": open_mouth}


def render(spec, shape, rgb=None, proj_dir=None):
    s = spec["synthetic"]
    if s["type"] == "ref_patch":
        return ref_patch(shape, s, rgb, proj_dir)
    if s["type"] == "eyelid":
        return eyelid(shape, s, rgb)
    return RENDERERS[s["type"]](shape, s)
