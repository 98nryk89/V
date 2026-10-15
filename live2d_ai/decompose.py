"""Split a flattened illustration into layers ("parts") from a declarative spec.

Spec (list of part dicts), drawn back->front by ``z``:
  id      unique name
  z       draw order (bigger = in front)
  zone    polygon or list of polygons [[x,y],...]: where this part may claim visible pixels
  color   optional colour gate: {"near": [[r,g,b],..], "tol": 14}  keep pixels close to a colour
                                {"far":  [[r,g,b],..], "tol": 14}  keep pixels far from all colours
  extent  optional polygon(s): the part's *full* shape including areas hidden behind front parts
          (those hidden pixels are reconstructed by inpainting). Default: no amodal extension.
  bleed   px of under-lap hidden behind front neighbours so no seam opens when parts move (default 8)
  over    id of the base part this layer sits on with *semi-transparent* pixels (hair strands over
          skin): alpha is solved from colour projection instead of a hard cut.

Pixels belong to the front-most part whose zone+colour claims them; everything is conserved so that
compositing all parts reproduces the source image.
"""
import numpy as np
import cv2
from scipy import ndimage as ndi


def polys(spec):
    if spec is None:
        return []
    if len(spec) and isinstance(spec[0][0], (int, float)):
        return [spec]
    return spec


def poly_mask(shape, spec, feather=0.8):
    h, w = shape
    m = np.zeros((h, w), np.float32)
    S = 4
    for p in polys(spec):
        big = np.zeros((h * S, w * S), np.uint8)
        pts = (np.array(p, np.float32) * S).astype(np.int32)
        cv2.fillPoly(big, [pts], 255)
        m = np.maximum(m, cv2.resize(big, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255)
    return m


def lab_of(rgb_u8):
    return cv2.cvtColor(rgb_u8, cv2.COLOR_RGB2LAB).astype(np.float32)


def color_gate(rgb_u8, rule):
    if not rule:
        return 1.0
    lab = lab_of(rgb_u8)
    tol = float(rule.get("tol", 14))
    key = "near" if "near" in rule else "far"
    cols = np.array(rule[key], np.uint8).reshape(-1, 1, 3)
    ref = cv2.cvtColor(cols, cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
    d = np.min(np.linalg.norm(lab[:, :, None, :] - ref[None, None], axis=3), axis=2)
    soft = np.clip((tol * 1.4 - d) / (tol * 0.4), 0, 1)
    return soft if key == "near" else 1 - soft


def push_pull_fill(rgb, known, levels=7):
    """Smoothly propagate colours from `known` (bool) into the rest (multi-scale push-pull)."""
    h, w = known.shape
    num = rgb.astype(np.float32) * known[..., None]
    den = known.astype(np.float32)
    pyr = [(num, den)]
    for _ in range(levels):
        n, d = pyr[-1]
        if min(n.shape[:2]) < 4:
            break
        pyr.append((cv2.resize(n, (n.shape[1] // 2, n.shape[0] // 2), interpolation=cv2.INTER_AREA),
                    cv2.resize(d, (d.shape[1] // 2, d.shape[0] // 2), interpolation=cv2.INTER_AREA)))
    est = None
    for n, d in reversed(pyr):
        cur = n / np.maximum(d[..., None], 1e-6)
        if est is not None:
            up = cv2.resize(est, (n.shape[1], n.shape[0]), interpolation=cv2.INTER_LINEAR)
            wgt = np.clip(d[..., None] * 4, 0, 1)
            cur = cur * wgt + up * (1 - wgt)
        est = cur
    return est


def fill_hidden(rgb, known, hidden, method="pushpull"):
    """Return rgb with `hidden` pixels reconstructed from `known` pixels."""
    if not hidden.any():
        return rgb
    if known.sum() < 10:
        return rgb
    pp = push_pull_fill(rgb, known)
    out = rgb.astype(np.float32).copy()
    # small holes: Telea keeps local detail better than a blurry push-pull
    hm = hidden.astype(np.uint8) * 255
    dist = ndi.distance_transform_edt(hidden)
    small = hidden & (dist <= 3)
    if small.any():
        te = cv2.inpaint(rgb.astype(np.uint8), (small * 255).astype(np.uint8), 3, cv2.INPAINT_TELEA)
        out[small] = te[small]
    big = hidden & ~small
    out[big] = pp[big]
    return out


def decompose(rgb_u8, alpha, specs, report=None):
    """rgb_u8: HxWx3 uint8 (RGB), alpha: HxW float. Returns {id: dict(rgba=full-canvas float RGBA, ...)}."""
    h, w = alpha.shape
    order = sorted(specs, key=lambda s: -s["z"])  # front first
    remaining = alpha.astype(np.float32).copy()
    vis = {}
    for s in order:
        zone = poly_mask((h, w), s["zone"]) if s.get("zone") is not None else np.ones((h, w), np.float32)
        gate = color_gate(rgb_u8, s.get("color"))
        a = np.minimum(remaining, zone * gate * (alpha > 0))
        if "min_alpha" in s:
            a = np.where(a > s["min_alpha"], a, 0)
        vis[s["id"]] = a
        remaining = remaining - a
    # anything unclaimed goes to the back-most part
    back = order[-1]["id"]
    vis[back] = vis[back] + np.maximum(remaining, 0)

    ids_front_first = [s["id"] for s in order]
    zmap = {s["id"]: s["z"] for s in specs}
    out = {}
    src = rgb_u8.astype(np.float32)
    for s in specs:
        pid = s["id"]
        v = vis[pid]
        front = np.zeros((h, w), np.float32)
        for o in ids_front_first:
            if zmap[o] > zmap[pid]:
                front = np.maximum(front, vis[o])
        solid = v > 0.5
        hidden = np.zeros((h, w), bool)
        ext = s.get("extent")
        if ext is not None:
            em = poly_mask((h, w), ext) > 0.5
            hidden |= em & (front > 0.5) & ~solid
        bleed = int(s.get("bleed", 8))
        if bleed > 0 and solid.any():
            near = ndi.binary_dilation(solid, iterations=bleed)
            hidden |= near & (front > 0.5) & ~solid
        # source colour for this part: its own visible pixels, hidden ones inpainted
        known = v > 0.05
        col = fill_hidden(src, known & ~hidden, hidden & ~known)
        a = np.clip(v, 0, 1)
        # alpha of the part as it sits in the stack: undo the 'over' compositing of conserved alpha
        a_layer = np.where(front < 0.999, a / np.maximum(1 - front, 1e-3), a)
        a_layer = np.clip(a_layer, 0, 1)
        a_layer = np.where(hidden, 1.0, a_layer)
        out[pid] = dict(rgb=col, alpha=a_layer, visible=v, hidden=hidden)
    return out


def bbox_of(alpha, pad=4, thr=0.01):
    ys, xs = np.where(alpha > thr)
    if len(xs) == 0:
        return None
    h, w = alpha.shape
    return (max(int(xs.min()) - pad, 0), max(int(ys.min()) - pad, 0),
            min(int(xs.max()) + 1 + pad, w), min(int(ys.max()) + 1 + pad, h))
