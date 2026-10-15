"""Build a runnable model (parts PNG + rig.json) from parts_spec.json + rig_spec.json."""
import json, os, sys, copy
import numpy as np
import cv2
from scipy import ndimage as ndi
from .decompose import decompose, bbox_of, push_pull_fill
from .synth import render as synth_render


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
    layers = decompose(rgb, alpha, pspec["parts"])
    templates = rspec.get("templates", {})
    rig_parts = []
    for ps in pspec["parts"]:
        pid = ps["id"]
        if "synthetic" in ps:
            rgb_s, a_s = synth_render(ps, (H, W))
            L = dict(rgb=rgb_s, alpha=a_s)
        else:
            L = layers[pid]
        bb = bbox_of(L["alpha"], pad=3)
        if bb is None:
            if verbose: print("  (empty part skipped)", pid)
            continue
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
