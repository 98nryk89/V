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
    # Change pupil movement only. Preserve all textures, masks and geometry.
    changed=[]
    for part in rig['parts']:
        if part['id'] not in ['eyeL_iris','eyeR_iris','eyeL_surprise_iris','eyeR_surprise_iris']:continue
        for effect in part.get('effects',[]):
            if effect.get('gaze') and effect.get('param')=='AngleY':
                effect['map']=[[-10,0,1],[0,0,0],[5,0,-3]];changed.append(part['id'])
    assert len(changed)==4
    html = (ROOT / 'viewer/iphone-motion-v4.html').read_text(encoding='utf-8')
    for name in ['runtime.js', 'iphone-motion-v4.js', 'tracking-input-v4.js']:
        html = html.replace(f'<script src="{name}"></script>', '<script>' + (ROOT / 'viewer' / name).read_text(encoding='utf-8') + '</script>')
    html = html.replace('<script>\n(async()=>{', '<script>window.__RIG__=' + json.dumps(rig, separators=(',', ':')) + ';</script>\n<script>\n(async()=>{', 1)
    assert 'window.__RIG__=' in html
    (ROOT / 'dist/owl_prince_iphone_motion_v4.html').write_text(html, encoding='utf-8')
    config = ROOT / 'dist/owl_prince_tracking_config_v4.json'
    if not config.exists():
        previous = json.loads((ROOT / 'dist/owl_prince_tracking_config_v3.json').read_text())
        previous['pitchLeakRatio']=.75
        config.write_text(json.dumps(previous, ensure_ascii=False, indent=2) + '\n')
    print('Motion v4:',len(rig['parts']),'parts; only four iris gaze maps changed; original SHA256',hashlib.sha256(source.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
