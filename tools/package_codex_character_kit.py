"""Portable instructions, generic source, and the unchanged approved model example."""
from hashlib import sha256
from html import escape
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs/codex-character-kit'
ARCHIVE = ROOT / 'dist/codex_character_creation_kit.zip'
BASELINE = '6a5e70a5f69bfcb85706e82e5ffa9149319b78d9'


def main():
    files = {}

    def add(name, content):
        assert name not in files, name
        files[name] = content.encode('utf-8') if isinstance(content, str) else content

    add('00_最初にお読みください.txt', (DOCS / '00_README.txt').read_bytes())
    guides = sorted(p for p in DOCS.iterdir() if p.name[0:2].isdigit())
    sections = []
    for index, path in enumerate(guides):
        content = path.read_text(encoding='utf-8')
        add('instructions/' + path.name, content)
        sections.append(f'<section id="s{index}"><h2>{escape(path.stem)}</h2><pre>{escape(content)}</pre></section>')
    links = ''.join(f'<li><a href="#s{i}">{escape(path.stem)}</a></li>' for i, path in enumerate(guides))
    add('読むための指示書.html', '<!doctype html><html lang="ja"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>別キャラ制作・Codex指示書</title>'
        '<style>body{max-width:960px;margin:30px auto;padding:0 20px;font:16px/1.8 system-ui,sans-serif;color:#222}'
        'pre{white-space:pre-wrap;overflow-wrap:anywhere;font:15px/1.9 system-ui,sans-serif;background:#f6f5fa;padding:18px}'
        'a{color:#4939b5}h2{margin-top:2em}section{border-top:1px solid #ddd;margin-top:35px}'
        '@media print{nav{display:none}pre{background:white}}</style></head><body>'
        '<h1>別キャラ制作・調整用 Codex指示書</h1><p>2026年10月21日。まず00を読み、01の指示全文をCodexへ貼り付けてください。</p>'
        '<nav><ol>' + links + '</ol></nav>' + ''.join(sections) + '</body></html>')
    for folder in ['live2d_ai']:
        for path in sorted((ROOT / folder).glob('*.py')):
            add('starter/' + path.relative_to(ROOT).as_posix(), path.read_bytes())
    for name in ['viewer/index.html', 'viewer/runtime.js', 'viewer/tracking.js', 'requirements.txt',
                 'tools/zoom.py', 'tools/preview.py', 'tools/fidelity.py', 'tests/tracking.test.cjs']:
        add('starter/' + name, (ROOT / name).read_bytes())
    # The unchanged regression test reads this original angle-limit fixture.
    add('starter/projects/owl_prince/rig_spec.json', (ROOT / 'projects/owl_prince/rig_spec.json').read_bytes())
    add('starter/projects/owl_prince/README.txt',
        'このrig_spec.jsonは同梱追跡テストが角度上限を読むための参照fixtureです。\n'
        '画像・マスクがないため、このフォルダはbuildできません。新キャラは別のIDに作ってください。\n')
    add('starter/AGENTS.md', (DOCS / 'starter-AGENTS.md').read_bytes())
    add('starter/README.md', '# 別キャラ制作用スターター\n\n'
        'このフォルダが作業ルートです。同梱キットのinstructions、AGENTS.md、記入済み制作依頼シートを読んでください。\n\n'
        '新キャラの画像をcharacter_materials/<新ID>/へ置き、projects/<新ID>/へ制作します。'
        'python -m live2d_ai initは一パーツの雛形を作るだけです。顔・髪・耳・口・目の分割とリグは別途必要です。\n\n'
        'セットアップとコマンドは../instructions/07_開発環境セットアップ.md、最初の依頼は'
        '../instructions/01_Codexへの最初の指示.txtを参照してください。\n\n'
        '元キャラ用の画像・専用マスク・全テスト・iPhone中継は未同梱。'
        '同梱tests/tracking.test.cjsはWebカメラの純粋な処理だけを検証します。\n')
    add('starter/.gitignore', '.venv/\n__pycache__/\n*.pyc\nprojects/*/out/\n')
    add('starter/character_materials/ここに新キャラ素材を置く.txt',
        '新キャラごとにフォルダを作り、元絵・差分・記入済みbrief.mdを置いてください。\n原本は上書きせず保持します。\n')
    add('reference/owl_prince.html', (ROOT / 'dist/owl_prince.html').read_bytes())
    add('reference/見本の操作説明.html', (ROOT / 'docs/webcam-user-guide.html').read_bytes())
    for name in ['AGENTS.md', 'CLAUDE.md']:
        add('reference/original_' + name, (ROOT / name).read_bytes())
    for name in ['parts_spec.json', 'rig_spec.json', 'head_model.json']:
        add('reference/owl_prince_specs/' + name, (ROOT / 'projects/owl_prince' / name).read_bytes())
    add('reference/owl_prince_specs/README.txt',
        'JSONは既存キャラの構成を読むための参考です。専用の元画像・マスク・補完は未同梱のため、\n'
        'このフォルダをそのままbuildできません。見本の座標・色条件を別キャラへ単純コピーしないでください。\n')
    manifest = {'date': '2026-10-21', 'reference_commit': BASELINE,
                'files': {name: {'bytes': len(data), 'sha256': sha256(data).hexdigest()}
                          for name, data in sorted(files.items())}}
    add('MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    with ZipFile(ARCHIVE, 'w', ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            archive.writestr('Codex_Character_Kit/' + name, data)
    with ZipFile(ARCHIVE) as archive:
        assert archive.testzip() is None
        for name, expected in manifest['files'].items():
            assert sha256(archive.read('Codex_Character_Kit/' + name)).hexdigest() == expected['sha256']
    print(f'{ARCHIVE.name}: {ARCHIVE.stat().st_size:,} bytes, {len(files)} files')


if __name__ == '__main__':
    main()
