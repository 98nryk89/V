"""Build a runnable model (parts PNG + rig.json) from parts_spec.json + rig_spec.json."""
import json, os, sys, copy
import numpy as np
import cv2
from scipy import ndimage as ndi
from .decompose import decompose, bbox_of, push_pull_fill
from .synth import render as synth_render
from .headmodel import HeadModel


def expand_effects(effects, templates):
    out = []
    for e in effects:
        if isinstance(e, str):
            out.extend(expand_effects(templates[e[1:]], templates))
        else:
            out.append(copy.deepcopy(e))
    return out


def make_mesh(alpha_crop, x0, y0, step):
    h, w = alpha_crop.shape
    nx, ny = max(1, round(w / step)), max(1, round(h / step))
    xs = np.linspace(0, w, nx + 1)
    ys = np.linspace(0, h, ny + 1)
    cell = np.zeros((ny, nx), bool)
    for j in range(ny):
        for i in range(nx):
            sl = alpha_crop[int(ys[j]):max(int(ys[j + 1]), int(ys[j]) + 1), int(xs[i]):max(int(xs[i + 1]), int(xs[i]) + 1)]
            cell[j, i] = sl.size and sl.max() > 0.02
    cell = ndi.binary_dilation(cell, iterations=1)
    vid = -np.ones((ny + 1, nx + 1), int)
    verts, uvs, tris = [], [], []

    def vtx(j, i):
        if vid[j, i] < 0:
            vid[j, i] = len(verts) // 2
            verts.extend([x0 + float(xs[i]), y0 + float(ys[j])])
            uvs.extend([float(xs[i]) / w, float(ys[j]) / h])
        return int(vid[j, i])
    for j in range(ny):
        for i in range(nx):
            if cell[j, i]:
                a, b, c, d = vtx(j, i), vtx(j, i + 1), vtx(j + 1, i), vtx(j + 1, i + 1)
                tris.extend([a, b, c, b, d, c])
    return dict(verts=[round(v, 2) for v in verts], uvs=[round(u, 5) for u in uvs], tris=tris)


def _smoothstep(a, lo, hi):
    t = np.clip((a - lo) / max(hi - lo, 1e-6), 0, 1)
    return t * t * (3 - 2 * t)


def _edge_context(alpha, layers, edge):
    """Silhouette bookkeeping shared by all parts: where the figure ends, and which part owns each outline pixel."""
    fg = alpha > 0.5
    dist, idx = ndi.distance_transform_edt(~fg, return_indices=True)
    near_in = ndi.distance_transform_edt(fg)
    zone = (dist <= 3) | (near_in <= 3)              # a few px either side of the silhouette
    ids = [k for k, v in layers.items()]
    stack = np.stack([layers[k]["visible"] for k in ids])
    owner_map = np.argmax(stack, axis=0)             # part that owns each foreground pixel
    return dict(fg=fg, dist=dist, idx=idx, zone=zone, ids=ids, owner=owner_map[idx[0], idx[1]])


def _apply_edge(L, pid, ctx, edge):
    """Crisp silhouette for one part: steeper alpha at the figure edge, dark outline ring, mild unsharp mask."""
    rgb = L["rgb"].astype(np.float32).copy()
    a = L["alpha"].astype(np.float32).copy()
    st = edge.get("steepen")
    if st:
        a = np.where(ctx["zone"], _smoothstep(a, st[0], st[1]), a)
    ol = edge.get("outline")
    if ol and pid in edge.get("no_outline", []):
        ol = None                     # parts that already carry a clean outline in the art (ornaments) keep it as is
    if ol:
        mine = ctx["owner"] == ctx["ids"].index(pid)
        w = float(ol.get("width", 1.5))
        ring_a = np.clip(w + 0.5 - ctx["dist"], 0, 1) * float(ol.get("strength", 0.9))
        ring = mine & (ctx["dist"] > 0) & (ring_a > 0) & ~ctx["fg"]
        near = rgb[ctx["idx"][0], ctx["idx"][1]] * float(ol.get("darken", 0.4))
        if "color" in ol:
            near = np.broadcast_to(np.array(ol["color"], np.float32), near.shape)
        new_a = np.where(ring, np.maximum(a, ring_a), a)
        use = ring & (ring_a >= a)
        rgb = np.where(use[..., None], near, rgb)
        a = new_a
    sh = edge.get("sharpen")
    if sh and pid in edge.get("no_sharpen", []):
        sh = None
    if sh:
        blur = cv2.GaussianBlur(rgb, (0, 0), float(sh.get("sigma", 1.0)))
        rgb = np.clip(rgb + float(sh.get("amount", 0.5)) * (rgb - blur), 0, 255)
    return dict(L, rgb=rgb, alpha=a)


def build(proj_dir, out_dir=None, verbose=True):
    proj_dir = os.path.abspath(proj_dir)
    out_dir = out_dir or os.path.join(proj_dir, "out")
    os.makedirs(os.path.join(out_dir, "parts"), exist_ok=True)
    pspec = json.load(open(os.path.join(proj_dir, "parts_spec.json")))
    rspec = json.load(open(os.path.join(proj_dir, "rig_spec.json")))
    src = os.path.normpath(os.path.join(proj_dir, pspec["source"]))
    rgba = cv2.imread(src, cv2.IMREAD_UNCHANGED)
    if rgba.shape[2] == 3:      # flat image with baked-in checkerboard: matte it first
        from .matte import remove_checker_background
        a_, c_ = remove_checker_background(rgba)
        rgba = np.dstack([c_, (a_ * 255).astype(np.uint8)])
        cv2.imwrite(os.path.join(out_dir, "cutout.png"), rgba)
    rgb = rgba[..., 2::-1].copy()
    alpha = rgba[..., 3].astype(np.float32) / 255
    H, W = alpha.shape
    def _resolve(o):                    # {"mask": "relative.png"} -> absolute path from the project dir
        if isinstance(o, dict):
            if "mask" in o and not os.path.isabs(o["mask"]):
                o = dict(o, mask=os.path.normpath(os.path.join(proj_dir, o["mask"])))
            return {k: _resolve(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_resolve(v) for v in o]
        return o
    pspec = _resolve(pspec)
    layers = decompose(rgb, alpha, pspec["parts"], unmix=pspec.get("unmix"))
    edge = pspec.get("edge")
    if edge:
        edge_ctx = _edge_context(alpha, layers, edge)
    else:
        edge_ctx = None
    templates = rspec.get("templates", {})
    rig_parts = []
    hm = HeadModel(os.path.join(proj_dir, rspec["head_model"])) if rspec.get("head_model") else None
    for ps in pspec["parts"]:
        pid = ps["id"]
        if "synthetic" in ps:
            rgb_s, a_s = synth_render(ps, (H, W), rgb, proj_dir)
            L = dict(rgb=rgb_s, alpha=a_s)
        else:
            L = layers[pid]
        bb = bbox_of(L["alpha"], pad=3)
        if bb is None:
            if verbose: print("  (empty part skipped)", pid)
            continue
        if edge_ctx is not None and "synthetic" not in ps:
            L = _apply_edge(L, pid, edge_ctx, edge)
            bb = bbox_of(L["alpha"], pad=3)
        x0, y0, x1, y1 = bb
        a = L["alpha"][y0:y1, x0:x1]
        col = L["rgb"][y0:y1, x0:x1]
        solid = a > 0.5
        col = push_pull_fill(col, solid) if (~solid).any() and solid.any() else col
        # keep true colours where the part exists
        col = np.where(solid[..., None], L["rgb"][y0:y1, x0:x1], col)
        tex = np.dstack([np.clip(col, 0, 255)[..., ::-1], a * 255]).astype(np.uint8)
        fn = f"parts/{pid}.png"
        cv2.imwrite(os.path.join(out_dir, fn), tex)
        rs = rspec.get("parts", {}).get(pid, {})
        step = rs.get("mesh_step", rspec.get("mesh_step", 24))
        part = dict(id=pid, tex=fn, z=ps["z"], bbox=[x0, y0, x1 - x0, y1 - y0],
                    mesh=make_mesh(a, x0, y0, step),
                    effects=expand_effects(rs.get("effects", []), templates))
        dspec = rs.get("depth")
        if dspec and hm is not None:
            vv = np.array(part["mesh"]["verts"], float).reshape(-1, 2)
            kw = {k: v for k, v in dspec.items() if k != "layer"}
            part["mesh"]["z"] = [round(float(z), 2) for z in hm.z(vv[:, 0], vv[:, 1], dspec["layer"], **kw)]
        for k in ("clip", "maskOnly", "opacity"):
            if k in rs:
                part[k] = rs[k]
        if "z" in rs:
            part["z"] = rs["z"]
        rig_parts.append(part)
        if verbose:
            print(f"  {pid:14s} bbox={x1-x0}x{y1-y0} verts={len(part['mesh']['verts'])//2}")
    rig = dict(size=[W, H], params=rspec["params"], parts=rig_parts, physics=rspec.get("physics", []),
               view=rspec.get("view"))
    json.dump(rig, open(os.path.join(out_dir, "rig.json"), "w"), separators=(",", ":"))
    return out_dir, layers


if __name__ == "__main__":
    build(sys.argv[1])
