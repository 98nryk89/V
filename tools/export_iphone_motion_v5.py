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
    # Preserve assets and rotation. Stop upward pupil motion; widen body travel.
    changed=[]
    for part in rig['parts']:
        if part['id'] not in ['eyeL_iris','eyeR_iris','eyeL_surprise_iris','eyeR_surprise_iris']:continue
        for effect in part.get('effects',[]):
            if effect.get('gaze') and effect.get('param')=='AngleY':
                effect['map']=[[-10,0,1],[0,0,0],[5,0,0]];changed.append(part['id'])
    assert len(changed)==4
    travel=0
    for part in rig['parts']:
        for effect in part.get('effects',[]):
            if effect.get('param')=='BodyX' and not effect.get('gaze') and effect.get('type')=='translate':
                assert effect['map']==[[-1,-90,0],[1,90,0]]
                effect['map']=[[-1,-135,0],[1,135,0]];travel+=1
    assert travel==52
    rig['view'][0]-=45;rig['view'][2]+=90
    html = (ROOT / 'viewer/iphone-motion-v5.html').read_text(encoding='utf-8')
    for name in ['runtime.js', 'iphone-motion-v4.js', 'tracking-input-v5.js']:
        html = html.replace(f'<script src="{name}"></script>', '<script>' + (ROOT / 'viewer' / name).read_text(encoding='utf-8') + '</script>')
    html = html.replace('<script>\n(async()=>{', '<script>window.__RIG__=' + json.dumps(rig, separators=(',', ':')) + ';</script>\n<script>\n(async()=>{', 1)
    assert 'window.__RIG__=' in html
    (ROOT / 'dist/owl_prince_iphone_motion_v5.html').write_text(html, encoding='utf-8')
    config = ROOT / 'dist/owl_prince_tracking_config_v5.json'
    if not config.exists():
        previous = json.loads((ROOT / 'dist/owl_prince_tracking_config_v4.json').read_text())
        config.write_text(json.dumps(previous, ensure_ascii=False, indent=2) + '\n')
    print('Motion v5:',len(rig['parts']),'parts; upward gaze off; horizontal travel +/-135px; original SHA256',hashlib.sha256(source.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
