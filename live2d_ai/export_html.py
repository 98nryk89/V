"""Bundle viewer + runtime + a built model into ONE self-contained html file (textures as data URIs)."""
import base64, json, os, re


def export_html(model_dir, out_path, viewer_dir=None, title="live2d_ai model"):
    viewer_dir = viewer_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "viewer")
    rig = json.load(open(os.path.join(model_dir, "rig.json")))
    for part in rig["parts"]:
        b = open(os.path.join(model_dir, part["tex"]), "rb").read()
        part["tex"] = "data:image/png;base64," + base64.b64encode(b).decode()
    html = open(os.path.join(viewer_dir, "index.html"), encoding="utf-8").read()
    rt = open(os.path.join(viewer_dir, "runtime.js"), encoding="utf-8").read()
    tk = open(os.path.join(viewer_dir, "tracking.js"), encoding="utf-8").read()
    html = html.replace('<script src="runtime.js"></script>', "<script>" + rt + "</script>")
    html = html.replace('<script src="tracking.js"></script>', "<script>" + tk + "</script>")
    html = html.replace("<title>live2d_ai viewer</title>", f"<title>{title}</title>")
    inject = "<script>window.__RIG__=" + json.dumps(rig, separators=(",", ":")) + ";</script>"
    html = html.replace("<script>\nconst q=", inject + "\n<script>\nconst q=", 1)
    assert "__RIG__=" in html
    open(out_path, "w", encoding="utf-8").write(html)
    return os.path.getsize(out_path)
