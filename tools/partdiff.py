"""Which part draws a visible artefact? Render a pose with each part removed and report the pixel change inside a region.
usage: partdiff.py <proj> "PosX=-1,AngleY=-10" x,y,w,h   (region in source-image pixels)"""
import sys, os, json, shutil
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.preview import render_poses, ROOT

proj, pose, region = sys.argv[1], sys.argv[2], sys.argv[3]
pose = {k: float(v) for k, v in (x.split("=") for x in pose.split(","))}
out = os.path.join(proj, "out"); rig = json.load(open(os.path.join(out, "rig.json")))
PRE = os.environ.get("PRE_REMOVE", "").split(",")      # parts removed from every render (e.g. to look underneath)
rig["parts"] = [p for p in rig["parts"] if p["id"] not in PRE]
tmp = os.path.join(ROOT, ".partdiff"); shutil.rmtree(tmp, ignore_errors=True)
variants = [("ALL", None)] + [(p["id"], p["id"]) for p in rig["parts"]]
files = []
for name, rm in variants:
    d = os.path.join(tmp, name); os.makedirs(d)
    os.symlink(os.path.abspath(os.path.join(out, "parts")), os.path.join(d, "parts"))
    r = dict(rig, parts=[p for p in rig["parts"] if p["id"] != rm]); json.dump(r, open(os.path.join(d, "rig.json"), "w"))
    f = render_poses(d, [("p", pose)], os.path.join(d, "r"), view=region)[0]; files.append((name, f))
base = np.asarray(Image.open(files[0][1]).convert("RGBA"), float)
Image.open(files[0][1]).resize((base.shape[1] * 3, base.shape[0] * 3)).save("/tmp/pv/partdiff_all.png")
res = []
for name, f in files[1:]:
    im = np.asarray(Image.open(f).convert("RGBA"), float)
    res.append((np.abs(im - base).sum(), name))
for v, n in sorted(res, reverse=True)[:10]: print(f"{n:16s} {v:10.0f}")
shutil.rmtree(tmp, ignore_errors=True)
