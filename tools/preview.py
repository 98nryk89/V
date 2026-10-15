"""Headless preview: render poses of a built model to PNGs (and a contact sheet) with Chromium+WebGL."""
import sys, os, json, threading, http.server, socketserver, functools, argparse
from playwright.sync_api import sync_playwright
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def serve():
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
    h.log_message = lambda *a, **k: None
    srv = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv

def render_poses(model_dir, poses, out_prefix, size=(700, 860), settle=0, crop=None):
    srv = serve(); port = srv.server_address[1]
    files = []
    with sync_playwright() as p:
        exe = next((c for c in ("/opt/pw-browsers/chromium-1194/chrome-linux/chrome",) if os.path.exists(c)), None)
        b = p.chromium.launch(executable_path=exe, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        pg = b.new_page(viewport={"width": size[0] + 320, "height": size[1]})
        logs = []
        pg.on("console", lambda m: logs.append(m.text)); pg.on("pageerror", lambda e: logs.append("ERR " + str(e)))
        rel = os.path.relpath(model_dir, ROOT)
        pg.goto(f"http://127.0.0.1:{port}/viewer/index.html?still=1&model=../{rel}")
        pg.wait_for_function("window.READY===true", timeout=60000)
        for i, (name, params) in enumerate(poses):
            pg.evaluate("p=>{M.reset();M.setParams(p);M.renderStill(%d)}" % settle, params)
            f = f"{out_prefix}_{name}.png"
            pg.locator("#c").screenshot(path=f, omit_background=True)
            files.append(f)
        for l in logs: print("console:", l)
        b.close()
    srv.shutdown()
    return files

def sheet(files, out, cols=4, scale=0.5, bg=(43, 40, 54)):
    ims = [Image.open(f).convert("RGBA") for f in files]
    w, h = ims[0].size; w2, h2 = int(w * scale), int(h * scale)
    rows = (len(ims) + cols - 1) // cols
    S = Image.new("RGB", (w2 * cols, h2 * rows), bg)
    for i, im in enumerate(ims):
        im = im.resize((w2, h2), Image.LANCZOS)
        S.paste(im, ((i % cols) * w2, (i // cols) * h2), im)
    S.save(out)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("model"); ap.add_argument("--out", default="/tmp/preview")
    ap.add_argument("--poses", default="")
    a = ap.parse_args()
    poses = [("rest", {})]
    for s in filter(None, a.poses.split(";")):
        name, _, kv = s.partition(":")
        poses.append((name, {k: float(v) for k, v in (x.split("=") for x in kv.split(","))}))
    fs = render_poses(a.model, poses, a.out)
    sheet(fs, a.out + "_sheet.png")
    print(a.out + "_sheet.png")
