"""Export learned three-direction input; keep previous models and webcam unchanged."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / 'dist/owl_prince.html'
    original = source.read_text(encoding='utf-8')
    match = re.search(r'window\.__RIG__\s*=', original)
    rig, _ = json.JSONDecoder().raw_decode(original[match.end():].lstrip())
    html = (ROOT / 'viewer/iphone-motion-verified.html').read_text(encoding='utf-8')
    for name in ['runtime.js', 'iphone-motion.js', 'tracking-input-v3.js']:
        html = html.replace(f'<script src="{name}"></script>', '<script>' + (ROOT / 'viewer' / name).read_text(encoding='utf-8') + '</script>')
    html = html.replace('<script>\n(async()=>{', '<script>window.__RIG__=' + json.dumps(rig, separators=(',', ':')) + ';</script>\n<script>\n(async()=>{', 1)
    assert 'window.__RIG__=' in html
    (ROOT / 'dist/owl_prince_iphone_motion_v3.html').write_text(html, encoding='utf-8')
    config = ROOT / 'dist/owl_prince_tracking_config_v3.json'
    if not config.exists():
        previous = json.loads((ROOT / 'dist/owl_prince_tracking_config_v2.json').read_text())
        config.write_text(json.dumps(previous, ensure_ascii=False, indent=2) + '\n')
    print('Motion v3: exact approved rig,', len(rig['parts']), 'parts; original SHA256', hashlib.sha256(source.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
