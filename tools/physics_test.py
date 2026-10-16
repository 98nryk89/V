"""Measure physics outputs for a scripted head motion. usage: python tools/physics_test.py projects/<name>/out"""
import sys, os, glob, threading, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from preview import serve, ROOT
from playwright.sync_api import sync_playwright
def run(model_dir, motion="return {AngleX:5*Math.sin(t*4.4), AngleY:-3+6*Math.sin(t*2.8), AngleZ:3*Math.sin(t*3.1)}", secs=8):
    srv = serve(); port = srv.server_address[1]
    with sync_playwright() as p:
        exe = os.environ.get("CHROME_PATH") or sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))[0]
        b = p.chromium.launch(executable_path=exe, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        pg = b.new_page(viewport={"width": 900, "height": 700})
        pg.goto(f"http://127.0.0.1:{port}/viewer/index.html?still=1&model=../{os.path.relpath(os.path.abspath(model_dir), ROOT)}")
        pg.wait_for_function("window.READY===true", timeout=60000)
        res = pg.evaluate("""([m,secs])=>{ const f=new Function('t',m); M.reset(); M.auto={blink:false,breath:true,idle:true,physics:true};
          const names=M.rig.physics.map(x=>x.output), out={}; for(const n of names) out[n]=[]; const fps=60;
          for(let i=0;i<fps*secs;i++){ const t=i/fps; M.setParams(f(t)); M._drive(1/fps); for(const n of names) out[n].push(M.params[n]); } return out; }""", [motion, secs])
        b.close()
    srv.shutdown(); return res
if __name__ == "__main__":
    for n, v in run(sys.argv[1]).items():
        v = np.array(v); print(f"{n:12s} max|v|={np.abs(v).max():.2f}  p95={np.percentile(np.abs(v),95):.2f}")
