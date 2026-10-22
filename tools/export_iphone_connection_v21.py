"""Create connection v2.1 without overwriting approved webcam or previous iPhone HTML."""
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
    html = (ROOT / 'viewer/iphone-v21.html').read_text(encoding='utf-8')
    for name in ['runtime.js', 'tracking-input-v21.js']:
        html = html.replace(f'<script src="{name}"></script>', '<script>' + (ROOT / 'viewer' / name).read_text(encoding='utf-8') + '</script>')
    html = html.replace('<script>\n(async()=>{', '<script>window.__RIG__=' + json.dumps(rig, separators=(',', ':')) + ';</script>\n<script>\n(async()=>{', 1)
    assert 'window.__RIG__=' in html
    (ROOT / 'dist/owl_prince_iphone_v21.html').write_text(html, encoding='utf-8')
    config = ROOT / 'dist/owl_prince_tracking_config_v2.json'
    if not config.exists():
        previous = json.loads((ROOT / 'dist/owl_prince_tracking_config.json').read_text())
        previous.update(positionScale=.2, rotationDeadzone=.35, positionDeadzone=.1)
        config.write_text(json.dumps(previous, ensure_ascii=False, indent=2) + '\n')
    print('Connection v2.1: exact approved rig,', len(rig['parts']), 'parts; original SHA256', hashlib.sha256(source.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
