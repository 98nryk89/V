"""python -m live2d_ai <command>   (see README.md)"""
import argparse, json, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_PARAMS = [
    {"id": "AngleX", "min": -30, "max": 30, "default": 0, "label": "顔の向き 左右"},
    {"id": "AngleY", "min": -30, "max": 30, "default": 0, "label": "顔の向き 上下"},
    {"id": "AngleZ", "min": -30, "max": 30, "default": 0, "label": "首かしげ"},
    {"id": "EyeLOpen", "min": 0, "max": 1, "default": 1, "label": "左目 開閉"},
    {"id": "EyeROpen", "min": 0, "max": 1, "default": 1, "label": "右目 開閉"},
    {"id": "EyeBallX", "min": -1, "max": 1, "default": 0, "label": "視線 左右"},
    {"id": "EyeBallY", "min": -1, "max": 1, "default": 0, "label": "視線 上下"},
    {"id": "MouthOpen", "min": 0, "max": 1, "default": 0, "label": "口 開き"},
    {"id": "Breath", "min": 0, "max": 1, "default": 0, "label": "呼吸"},
    {"id": "IdleX", "min": -1, "max": 1, "default": 0, "hidden": True},
    {"id": "IdleY", "min": -1, "max": 1, "default": 0, "hidden": True},
]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="live2d_ai")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="new project from one illustration"); p.add_argument("image"); p.add_argument("project")
    p = sub.add_parser("matte", help="remove baked-in checkerboard background"); p.add_argument("image"); p.add_argument("-o", default="cutout.png")
    p = sub.add_parser("build", help="parts_spec.json + rig_spec.json -> out/ (parts, rig.json)"); p.add_argument("project")
    p = sub.add_parser("zoom", help="crop+zoom with coordinate grid (for reading polygon coordinates)")
    p.add_argument("image"); p.add_argument("x0", type=int); p.add_argument("y0", type=int); p.add_argument("x1", type=int); p.add_argument("y1", type=int)
    p.add_argument("--scale", type=int, default=3); p.add_argument("--step", type=int, default=20); p.add_argument("-o", default="zoom.png")
    p = sub.add_parser("labels", help="colour overlay showing which part claims which pixel"); p.add_argument("project"); p.add_argument("-o", default="labels.png")
    p = sub.add_parser("preview", help="headless render of poses to a contact sheet")
    p.add_argument("project"); p.add_argument("--poses", default=""); p.add_argument("--view"); p.add_argument("--out", default="preview")
    p.add_argument("--cols", type=int, default=4); p.add_argument("--scale", type=float, default=0.5)
    p = sub.add_parser("export", help="single self-contained html"); p.add_argument("project"); p.add_argument("-o", default=None)
    p = sub.add_parser("serve", help="serve the viewer locally"); p.add_argument("project"); p.add_argument("--port", type=int, default=8000)
    a = ap.parse_args(argv)
    sys.path.insert(0, ROOT)

    if a.cmd == "init":
        os.makedirs(a.project, exist_ok=True)
        shutil.copy(a.image, os.path.join(a.project, "source.png" if a.image.lower().endswith("png") else os.path.basename(a.image)))
        src = "source.png" if a.image.lower().endswith("png") else os.path.basename(a.image)
        json.dump({"source": src, "parts": [{"id": "body", "z": 0, "zone": None}]}, open(os.path.join(a.project, "parts_spec.json"), "w"), indent=1)
        json.dump({"mesh_step": 20, "params": DEFAULT_PARAMS, "templates": {}, "parts": {}, "physics": []}, open(os.path.join(a.project, "rig_spec.json"), "w"), indent=1)
        print("created", a.project, "- now look at the image, add parts to parts_spec.json (see CLAUDE.md)")
    elif a.cmd == "matte":
        import cv2, numpy as np
        from live2d_ai.matte import remove_checker_background
        im = cv2.imread(a.image)
        al, col = remove_checker_background(im)
        cv2.imwrite(a.o, np.dstack([col, (al * 255).astype(np.uint8)])); print("wrote", a.o)
    elif a.cmd == "build":
        from live2d_ai.build import build
        print("built", build(a.project)[0])
    elif a.cmd == "zoom":
        sys.path.insert(0, os.path.join(ROOT, "tools")); import zoom
        zoom.zoom(a.image, a.x0, a.y0, a.x1, a.y1, a.scale, a.step, a.o); print("wrote", a.o)
    elif a.cmd == "labels":
        import cv2
        from live2d_ai.decompose import decompose
        from live2d_ai.viz import label_overlay
        sp = json.load(open(os.path.join(a.project, "parts_spec.json")))
        src = os.path.normpath(os.path.join(a.project, sp["source"]))
        im = cv2.imread(src, cv2.IMREAD_UNCHANGED)
        if im.shape[2] == 3:
            import numpy as np
            from live2d_ai.matte import remove_checker_background
            al, col = remove_checker_background(im); im = np.dstack([col, (al * 255).astype(np.uint8)])
        rgb = im[..., 2::-1].copy(); out = decompose(rgb, im[..., 3] / 255., sp["parts"])
        ids = [q["id"] for q in sp["parts"] if "synthetic" not in q]
        cv2.imwrite(a.o, label_overlay(rgb, {k: v["visible"] for k, v in out.items()}, ids, 0.6)[..., ::-1]); print("wrote", a.o)
    elif a.cmd == "preview":
        sys.path.insert(0, os.path.join(ROOT, "tools")); import preview
        poses = [("rest", {})]
        for s in filter(None, a.poses.split(";")):
            name, _, kv = s.partition(":"); poses.append((name, {k: float(v) for k, v in (x.split("=") for x in kv.split(","))}))
        fs = preview.render_poses(os.path.join(os.path.abspath(a.project), "out"), poses, a.out, view=a.view)
        preview.sheet(fs, a.out + "_sheet.png", cols=a.cols, scale=a.scale); print("wrote", a.out + "_sheet.png")
    elif a.cmd == "export":
        from live2d_ai.export_html import export_html
        out = a.o or os.path.join(a.project, "model.html")
        print("wrote", out, export_html(os.path.join(a.project, "out"), out) // 1024, "KB")
    elif a.cmd == "serve":
        import http.server, socketserver, functools
        rel = os.path.relpath(os.path.join(os.path.abspath(a.project), "out"), ROOT)
        h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
        print(f"open http://localhost:{a.port}/viewer/index.html?model=../{rel}")
        socketserver.TCPServer.allow_reuse_address = True
        socketserver.TCPServer(("", a.port), h).serve_forever()


if __name__ == "__main__":
    main()
