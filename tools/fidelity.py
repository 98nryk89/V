"""Rest-pose fidelity: render the built model at rest in headless Chromium and compare to the source cutout."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, cv2
from preview import render_poses

def fidelity(model_dir, cutout, out='/tmp/fid', regions=None):
    src = cv2.imread(cutout, cv2.IMREAD_UNCHANGED)
    H, W = src.shape[:2]
    f = render_poses(model_dir, [('rest', {})], out, view=f'0,0,{W},{H}', size=(W, H))[0]
    r = cv2.imread(f).astype(np.float32)
    bg = np.array([54, 40, 43], np.float32); a = src[..., 3:] / 255.
    o = src[..., :3] * a + bg * (1 - a)
    def psnr(m):
        d = ((r - o) ** 2)[m]; return 10 * np.log10(255 ** 2 / max(d.mean(), 1e-6))
    res = {'full': psnr(np.ones((H, W), bool))}
    for name, (x0, y0, x1, y1) in (regions or {}).items():
        m = np.zeros((H, W), bool); m[y0:y1, x0:x1] = True; res[name] = psnr(m)
    err = np.abs(r - o).max(2)
    return res, err

if __name__ == '__main__':
    res, err = fidelity(sys.argv[1], sys.argv[2], regions={'face': (400, 230, 760, 580), 'eyes': (430, 355, 710, 410)})
    print({k: round(float(v), 2) for k, v in res.items()})
    cv2.imwrite(sys.argv[3] if len(sys.argv) > 3 else '/tmp/fid_err.png', np.clip(err * 4, 0, 255).astype(np.uint8))
