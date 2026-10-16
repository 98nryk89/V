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


def _ellipse_poly(cx, cy, rx, ry, deg=0, n=64):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    c, s_ = np.cos(np.radians(deg)), np.sin(np.radians(deg))
    x, y = rx * np.cos(t), ry * np.sin(t)
    return [[cx + x[i] * c - y[i] * s_, cy + x[i] * s_ + y[i] * c] for i in range(n)]


def polys(spec):
    """Normalise to a list of polygons. Accepts a polygon, a list of polygons, {"ellipse":[cx,cy,rx,ry,deg]}."""
    if spec is None:
        return []
    if isinstance(spec, dict):
        spec = [spec]
    if len(spec) and isinstance(spec[0], (int, float)):
        return []
    if len(spec) and isinstance(spec[0], (list, tuple)) and len(spec[0]) == 2 and isinstance(spec[0][0], (int, float)):
        return [spec]
    out = []
    for item in spec:
        if isinstance(item, dict):
            out.append(_ellipse_poly(*item["ellipse"]))
        else:
            out.extend(polys(item) if not (len(item) and isinstance(item[0], (list, tuple)) and len(item[0]) == 2 and isinstance(item[0][0], (int, float))) else [item])
    return out


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
    """Soft 0..1 gate. rule: dict or list of dicts (AND).
    {"near":[rgb..],"tol":T} | {"far":[rgb..],"tol":T} | {"lab":{"L":[lo,hi],"a":[..],"b":[..]},"soft":s}"""
    if not rule:
        return 1.0
    if isinstance(rule, list):
        g = 1.0
        for r in rule:
            g = g * color_gate(rgb_u8, r)
        return g
    if "any" in rule:              # union of rules
        g = 0.0
        for r in rule["any"]:
            g = np.maximum(g, color_gate(rgb_u8, r))
        return g
    lab = lab_of(rgb_u8)
    if "lab" in rule:
        soft = float(rule.get("soft", 3))
        g = np.ones(lab.shape[:2], np.float32)
        for ch, name in enumerate("Lab"):
            if name in rule["lab"]:
                lo, hi = rule["lab"][name]
                v = lab[..., ch]
                g = g * np.clip((v - lo) / soft + 0.5, 0, 1) * np.clip((hi - v) / soft + 0.5, 0, 1)
        return g
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
    specs = [s for s in specs if "synthetic" not in s]
    order = sorted(specs, key=lambda s: -s["z"])  # front first
    remaining = alpha.astype(np.float32).copy()
    vis = {}
    for s in order:
        zone = poly_mask((h, w), s["zone"]) if s.get("zone") is not None else np.ones((h, w), np.float32)
        if s.get("zone_grow"):      # let the part own a few px of outline just outside its polygon
            zone = np.maximum(zone, ndi.binary_dilation(zone > 0.5, iterations=int(s["zone_grow"])).astype(np.float32))
        gate = color_gate(rgb_u8, s.get("color"))
        a = zone * gate * (alpha > 0)
        if s.get("close"):          # bridge small gaps / fill pinholes (dark shading inside silver hair, ...)
            r = int(s["close"])
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
            m = cv2.morphologyEx((a > 0.5).astype(np.uint8), cv2.MORPH_CLOSE, k) > 0
            holes = ndi.binary_fill_holes(m) & ~m
            lab_h, nh = ndi.label(holes)
            if nh:
                sz = ndi.sum(holes, lab_h, range(1, nh + 1))
                m |= np.isin(lab_h, 1 + np.flatnonzero(sz <= int(s.get("fill_holes", 150))))
            a = np.maximum(a, m.astype(np.float32) * zone * (alpha > 0))
        a = np.minimum(remaining, a)
        if "min_alpha" in s:
            a = np.where(a > s["min_alpha"], a, 0)
        vis[s["id"]] = a
        remaining = remaining - a
    cleaned = {}
    for s_ in specs:
        c = s_.get("clean")
        if not c:
            continue
        v = vis[s_["id"]]
        gate = color_gate(rgb_u8, c["skin"])
        zone = poly_mask((h, w), s_["zone"]) if s_.get("zone") is not None else np.ones((h, w), np.float32)
        inner = ndi.distance_transform_edt(zone > 0.5) > float(c.get("margin", 6))
        protect = poly_mask((h, w), c["protect"]) > 0.5 if c.get("protect") else np.zeros((h, w), bool)
        bad = (v > 0.5) & (gate < 0.5) & inner & ~protect
        bad = ndi.binary_dilation(bad, iterations=int(c.get("grow", 1))) & (v > 0.05) & inner & ~protect
        cleaned[s_["id"]] = bad
        vis[s_["id"]] = np.where(bad, 0.0, v)
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
        if pid in cleaned:      # contaminated pixels: reconstruct as clean skin (alpha 1)
            hidden |= cleaned[pid]
        ext = s.get("extent")
        if ext is not None:
            em = (alpha > 0.5) if ext == "all" else poly_mask((h, w), ext) > 0.5
            hidden |= em & (front > 0.5) & ~solid
        bleed = int(s.get("bleed", 8))
        if bleed > 0 and solid.any():
            near = ndi.binary_dilation(solid, iterations=bleed)
            if ext is not None and ext != "all":      # under-lap only inside the part's true shape (no skin leaking past the contour)
                near &= ndi.binary_dilation(em, iterations=2)
            hidden |= near & (front > 0.5) & ~solid
        # source colour for this part: its own visible pixels, hidden ones inpainted
        known = v > 0.05
        if s.get("fill_gate"):      # only these pixels may seed the reconstruction of hidden areas
            known_src = known & (color_gate(rgb_u8, s["fill_gate"]) > 0.5)
        else:
            known_src = known
        if s.get("known_erode"):    # keep antialiased/contaminated rims out of the seed pixels
            known_src = ndi.binary_erosion(known_src, iterations=int(s["known_erode"]))
        if "fill_rgb" in s:
            col = src.copy()
            hm = ndi.gaussian_filter((hidden & ~known).astype(np.float32), 2.0)[..., None]
            col = col * (1 - hm) + np.array(s["fill_rgb"], np.float32) * hm
            col = np.where((hidden & ~known)[..., None], np.array(s["fill_rgb"], np.float32), col)
        else:
            col = fill_hidden(src, known_src & ~hidden, hidden & ~known)
            if s.get("fill_smooth"):   # hidden skin/hair should be smooth, not a copy of strand edges
                sg = float(s["fill_smooth"])
                hm_ = (hidden & ~known)
                if hm_.any():
                    blurred = np.stack([ndi.gaussian_filter(col[..., c] * hm_, sg) for c in range(3)], -1)
                    wgt = ndi.gaussian_filter(hm_.astype(np.float32), sg)[..., None]
                    sm = blurred / np.maximum(wgt, 1e-3)
                    col = np.where(hm_[..., None], np.where(wgt > 0.05, sm, col), col)
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
