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


RENDERERS = {"closed_eye": closed_eye, "open_mouth": open_mouth}


def render(spec, shape):
    s = spec["synthetic"]
    return RENDERERS[s["type"]](shape, s)
