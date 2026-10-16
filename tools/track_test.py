"""Closed-loop test of the webcam tracker (no camera needed).

The model is rendered at known poses, mirrored like a webcam selfie, fed to MediaPipe through viewer/tracking.js, and
the recovered parameters are compared with the commanded ones. If the tracker's signs/scales were wrong, the table
shows it. Needs a local copy of @mediapipe/tasks-vision and face_landmarker.task (the container cannot reach jsdelivr):

    npm pack @mediapipe/tasks-vision@0.10.14 && tar xzf *.tgz && mkdir mp && cp -r package/* mp/
    curl -o mp/face_landmarker.task https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task
    python tools/track_test.py projects/owl_prince/out mp
"""
import sys, os, json, threading, http.server, socketserver, functools
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
if os.environ.get("WIDE"):      # test-only: lift the model's angle limits to see sign and scale of the tracker clearly
    POSES = [("rest", {}), ("x+20", {"AngleX": 20}), ("x-20", {"AngleX": -20}), ("y+20", {"AngleY": 20}), ("y-20", {"AngleY": -20}),
             ("z+20", {"AngleZ": 20}), ("z-20", {"AngleZ": -20})]
else:
  POSES = [("rest", {}), ("x+7", {"AngleX": 7}), ("x-7", {"AngleX": -7}), ("y+7", {"AngleY": 7}), ("y-7", {"AngleY": -7}),
         ("z+7", {"AngleZ": 7}), ("z-7", {"AngleZ": -7}), ("x+4", {"AngleX": 4}), ("blink", {"EyeLOpen": 0, "EyeROpen": 0}),
         ("wink-L", {"EyeLOpen": 0}), ("wink-R", {"EyeROpen": 0}), ("mouth", {"MouthOpen": 1})]


def serve(mp_dir):
    class H(http.server.SimpleHTTPRequestHandler):
        def translate_path(self, path):
            if path.startswith("/mp/"):
                return os.path.join(mp_dir, path[4:].split("?")[0])
            return super().translate_path(path)
        def log_message(self, *a, **k):
            pass
    srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(H, directory=ROOT))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def run(model_dir, mp_dir, view="360,120,420,480"):
    srv = serve(os.path.abspath(mp_dir)); port = srv.server_address[1]
    rel = os.path.relpath(os.path.abspath(model_dir), ROOT)
    rows = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=EXE, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        pg = b.new_page(viewport={"width": 1020, "height": 700})
        pg.add_init_script("window.L2D_MP={cdn:'/mp',model:'/mp/face_landmarker.task'}")
        pg.on("pageerror", lambda e: print("pageerror", e))
        pg.goto(f"http://127.0.0.1:{port}/viewer/index.html?still=1&model=../{rel}&view={view}")
        pg.wait_for_function("window.READY===true", timeout=60000)
        pg.evaluate("""async () => {
          window.OUT = {}; const dummy = {setParam:(k,v)=>{window.OUT[k]=v}};
          window.T = new L2DTracker(dummy, {smooth: 0});
          await T.load('CPU');
          window.TS = 1000;
          window.shot = (pose) => {
            M.reset(); M.setParams(pose); M.renderStill(0);
            const src = document.getElementById('c');
            const c = document.createElement('canvas'); c.width = src.width; c.height = src.height;
            const g = c.getContext('2d'); g.fillStyle = '#2b2836'; g.fillRect(0,0,c.width,c.height);
            g.translate(c.width, 0); g.scale(-1, 1); g.drawImage(src, 0, 0);       // selfie mirror
            window.OUT = {}; let ok = false;
            for (let i = 0; i < 2; i++) { TS += 33; ok = T.feed(c, TS); }
            const m = T.lastMatrix; const o = ok ? Object.assign({}, window.OUT) : null; if (o && m) { o.m = m; o.rawyaw = T.raw.yaw; o.rawpitch = T.raw.pitch; } return o;
          };
        }""")
        if os.environ.get("WIDE"):
            pg.evaluate("for (const k of ['AngleX','AngleY','AngleZ']) { M.paramDefs[k].min = -30; M.paramDefs[k].max = 30; }")
        pg.evaluate("shot({})")
        pg.evaluate("T.calibrate()")                       # what the UI button does
        for name, pose in POSES:
            rows.append((name, pose, pg.evaluate("p => shot(p)", pose)))
        b.close()
    srv.shutdown()
    return rows


if __name__ == "__main__":
    rows = run(sys.argv[1], sys.argv[2])
    keys = ["AngleX", "AngleY", "AngleZ", "EyeLOpen", "EyeROpen", "MouthOpen"]
    import math
    def eul(m):                                  # column-major 4x4 -> yaw, pitch, roll (deg)
        R = [[m[0], m[4], m[8]], [m[1], m[5], m[9]], [m[2], m[6], m[10]]]
        yaw = math.degrees(math.atan2(R[0][2], R[2][2]))
        pitch = math.degrees(math.atan2(-R[1][2], math.hypot(R[0][2], R[2][2])))
        roll = math.degrees(math.atan2(R[1][0], R[1][1]))
        return yaw, pitch, roll
    if os.environ.get("EULER"):
        for name, pose, out in rows:
            if out and "m" in out:
                y, pt, r = eul(out["m"]); print(f"{name:8s} yaw {y:7.2f} pitch {pt:7.2f} roll {r:7.2f}  rawyaw {out['rawyaw']:.3f} rawpitch {out['rawpitch']:.3f}  cmd={json.dumps(pose)}")
        sys.exit()
    print(f"{'pose':8s} " + " ".join(f"{k:>9s}" for k in keys))
    for name, pose, out in rows:
        if out is None:
            print(f"{name:8s} (no face detected)"); continue
        print(f"{name:8s} " + " ".join(f"{out.get(k, float('nan')):9.2f}" for k in keys) + "   cmd=" + json.dumps(pose))
