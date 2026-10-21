"""Create a separate input test bundle using the approved HTML's exact embedded rig.

Does not build the model or modify the original three HTML files or images.
"""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / 'dist/owl_prince.html'
    original = source.read_text(encoding='utf-8')
    match = re.search(r'window\.__RIG__\s*=', original)
    if not match:
        raise ValueError('Approved HTML has no embedded rig')
    rig, _ = json.JSONDecoder().raw_decode(original[match.end():].lstrip())
    html = (ROOT / 'viewer/iphone-test.html').read_text(encoding='utf-8')
    for name in ['runtime.js', 'tracking-input.js']:
        code = (ROOT / 'viewer' / name).read_text(encoding='utf-8')
        html = html.replace(f'<script src="{name}"></script>', f'<script>{code}</script>')
    html = html.replace('<script>\n(async()=>{', '<script>window.__RIG__=' + json.dumps(rig, separators=(',', ':')) + ';</script>\n<script>\n(async()=>{', 1)
    assert 'window.__RIG__=' in html
    output = ROOT / 'dist/owl_prince_iphone_test.html'
    output.write_text(html, encoding='utf-8')
    (ROOT / 'dist/tracking_webcam_legacy.js').write_bytes((ROOT / 'viewer/tracking.js').read_bytes())
    config = ROOT / 'dist/owl_prince_tracking_config.json'
    if not config.exists():
        config.write_text(json.dumps({
            'wsUrl': 'ws://localhost:8765', 'smoothingMs': 80,
            'lostReturnMs': 500, 'staleMs': 750,
            'gainX': 1, 'gainY': 1, 'gainMove': 1, 'positionScale': 10,
            'invX': False, 'invY': False, 'invZ': False,
            'hotkeys': {'1': 'smile', '2': 'surprise', '3': 'neutral', '4': 'auto',
                        '5': 'none', '6': 'none', '7': 'none', '8': 'none'},
        }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{output.name}: {len(rig["parts"])} parts; approved source SHA256 {hashlib.sha256(source.read_bytes()).hexdigest()}')


if __name__ == '__main__':
    main()
