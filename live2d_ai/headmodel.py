"""Character-specific head depth model.

The head is described by *measurements of this character* (head_model.json), not a generic sphere:
  * width(y)    left/right half-widths of the face contour at each height (from the front art)
  * profile(y)  how far the face surface stands out from the rotation axis at each height (from the side art),
                with the nose as a separate narrow ridge
  * a few shells for hair / ornaments sitting on or around the head
z(x, y, layer) gives, for any pixel of the front art, its depth; the runtime rotates vertices with it.
"""
import json
import numpy as np


class HeadModel:
    def __init__(self, spec):
        if isinstance(spec, str):
            spec = json.load(open(spec))
        self.s = spec
        m = spec["side_to_front_y"]
        self._sy, self._fy = np.array(m["side"], float), np.array(m["front"], float)
        p = spec["side_profile"]
        ys = np.array(p["y"], float)
        self.prof_y = np.interp(ys, self._sy, self._fy)           # front-art y of each profile sample
        self.prof_z = np.array(p["x"], float) - spec["side_axis_x"]
        n = spec["nose"]
        self.nose_tip_y = float(np.interp(n["side_tip_y"], self._sy, self._fy))
        self.nose_top_y = float(np.interp(n["side_bridge_y"], self._sy, self._fy))
        self.nose_base_y = float(np.interp(n["side_base_y"], self._sy, self._fy))
        # base (nose-less) surface under the nose: straight line bridge -> upper lip
        z_bridge = float(np.interp(n["side_bridge_y"], ys, self.prof_z))
        z_base = float(np.interp(n["side_base_y"], ys, self.prof_z))
        tip_z = n["side_tip_x"] - spec["side_axis_x"]
        t = (n["side_tip_y"] - n["side_bridge_y"]) / (n["side_base_y"] - n["side_bridge_y"])
        self.nose_height = tip_z - (z_bridge + (z_base - z_bridge) * t)
        self.nose_hw = float(n["half_width"])
        w = spec["width"]
        self.wy = np.array(w["y"], float)
        self.wl, self.wr = np.array(w["left"], float), np.array(w["right"], float)
        self.xc, self.expo = float(w["xc"]), float(w.get("exponent", 2.4))

    # ---- measured curves ------------------------------------------------------------
    def depth_base(self, y):
        """Face depth without the nose, at front-art height y (clamped outside the measured range)."""
        d = np.interp(y, self.prof_y, self.prof_z)
        # remove the nose ridge from the measured profile between bridge and upper lip
        a, b = self.nose_top_y, self.nose_base_y
        zb = np.interp(a, self.prof_y, self.prof_z), np.interp(b, self.prof_y, self.prof_z)
        lin = zb[0] + (zb[1] - zb[0]) * np.clip((y - a) / (b - a), 0, 1)
        return np.where((y > a) & (y < b), lin, d)

    def nose_h(self, y):
        a, tip, b = self.nose_top_y, self.nose_tip_y, self.nose_base_y
        up = np.clip((y - a) / (tip - a), 0, 1)
        down = np.clip((b - y) / (b - tip), 0, 1)
        return self.nose_height * np.where(y < tip, up, down)

    def widths(self, y):
        return np.interp(y, self.wy, self.wl), np.interp(y, self.wy, self.wr)

    def inside(self, x, y):
        wl, wr = self.widths(y)
        u = x - self.xc
        return np.where(u < 0, -u / np.maximum(wl, 1e-3), u / np.maximum(wr, 1e-3))

    # ---- layers ---------------------------------------------------------------------
    def face(self, x, y, extra_w=0.0, extra_d=0.0):
        wl, wr = self.widths(y)
        u = x - self.xc
        wside = np.where(u < 0, wl, wr) + extra_w
        r = np.minimum(np.abs(u) / np.maximum(wside, 1e-3), 0.985)   # outside the contour: continue the edge value (no cliff)
        cs = np.clip(1 - r ** self.expo, 0, 1) ** (1 / self.expo)
        fl = float(self.s.get("edge_floor", 0.0))      # keep the contour from collapsing to zero depth: bounded texture stretch
        cs = fl + (1 - fl) * cs
        z = (self.depth_base(y) + extra_d) * cs
        nose = self.nose_h(y) * np.exp(-((u / self.nose_hw) ** 2))
        out = z + nose * cs
        # ears sit on the head's side plane, i.e. near the rotation axis: past the face contour the depth falls to a small
        # value, so ear skin / earring / side hair move together instead of the skin sliding over them
        ew = float(self.s.get("ear_taper", 0.0))
        if ew > 0:
            over = np.maximum(np.abs(u) - (wside - 6.0), 0.0)
            f = np.clip(1.0 - over / ew, float(self.s.get("ear_floor", 0.1)), 1.0)
            out = out * f
        return out

    def z(self, x, y, layer, **kw):
        x = np.asarray(x, float); y = np.asarray(y, float)
        L = layer
        if L == "face":
            return self.face(x, y) + kw.get("off", 0.0)
        if L == "hairfront":
            h = self.s["hair"]
            fo = np.interp(y, [p[0] for p in h["front_offset"]], [p[1] for p in h["front_offset"]])
            return self.face(x, y, extra_w=h["front_extra_width"], extra_d=fo) + kw.get("off", 0.0)
        if L == "dome":
            d = self.s["hair"]["dome"]
            r2 = ((x - d["cx"]) / d["rx"]) ** 2 + ((y - d["cy"]) / d["ry"]) ** 2
            return d["rz"] * np.sqrt(np.clip(1 - r2, 0.0, 1)) + kw.get("off", 0.0)
        if L == "side":
            h = self.s["hair"]["side"]
            wl, wr = self.widths(np.clip(y, self.wy[0], self.wy[-1]))
            u = x - self.xc
            ws = np.where(u < 0, wl, wr) + h["extra_width"]
            r = np.abs(u) / np.maximum(ws, 1e-3)
            return h["depth_ratio"] * self.depth_base(np.clip(y, 300, 556)) * np.sqrt(np.clip(1 - r ** 2, 0, 1)) + kw.get("off", 0.0)
        if L == "neck":
            n = self.s["neck"]
            r = (x - n["cx"]) / n["half_width"]
            return n["depth"] * np.sqrt(np.clip(1 - r ** 2, 0, 1)) + kw.get("off", 0.0)
        if L == "const":
            return np.full_like(x, kw.get("z", 0.0))
        raise ValueError(layer)
