"""Package the accepted MOTION-5 unchanged, instructions, and reusable source."""
from hashlib import sha256
from html import escape
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs/motion5-character-kit'
BASELINE = '91f240f75a437830697126397fce60a8202b6b16'
PREFIX = 'Codex_MOTION5_Character_Kit/'


def main():
    files = {}

    def add(name, data):
        assert name not in files
        files[name] = data.encode('utf-8') if isinstance(data, str) else data

    def copy(name, source):
        add(name, (ROOT / source).read_bytes())

    guides = sorted(DOCS.glob('[0-9][0-9]_*'))
    sections = []
    for guide in guides:
        copy('instructions/' + guide.name, guide.relative_to(ROOT))
        sections.append('<section><h2>' + escape(guide.stem) + '</h2><pre>' +
                        escape(guide.read_text()) + '</pre></section>')
    copy('00_最初にお読みください.txt', 'docs/motion5-character-kit/00_最初にお読みください.txt')
    add('読むための指示書.html', '<!doctype html><html lang="ja"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>MOTION-5・別キャラ制作指示書</title><style>'
        'body{max-width:960px;margin:30px auto;padding:0 20px;font:16px/1.8 system-ui;color:#222}'
        'pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;background:#f5f5fa;padding:20px}'
        'section{margin:40px 0;border-top:1px solid #ccc}</style>'
        '<h1>MOTION-5・別キャラ制作指示書</h1>' + ''.join(sections) + '</html>')
    for source in sorted((ROOT / 'live2d_ai').glob('*.py')):
        copy('starter/' + source.relative_to(ROOT).as_posix(), source.relative_to(ROOT))
    for source in ['requirements.txt', 'viewer/index.html', 'viewer/runtime.js', 'viewer/tracking.js',
                   'tools/zoom.py', 'tools/preview.py', 'tools/fidelity.py']:
        copy('starter/' + source, source)
    for name in ['AGENTS', 'CLAUDE']:
        copy(f'starter/{name}.md', f'docs/motion5-character-kit/starter-{name}.md')
    add('starter/.gitignore', '.venv/\n__pycache__/\n*.pyc\nnode_modules/\nprojects/*/out/\n.DS_Store\n')
    add('starter/character_materials/README.txt', '新IDのフォルダへ元絵・差分・記入済み制作依頼シートを置きます。原本は保持します。\n')
    add('starter/README.md', '# 新キャラ制作ルート\n\n'
        'instructionsとreference_sourcesをこのルートへコピーしてから、制作依頼シートとAGENTS.mdを読んでください。\n'
        '同梱は共通制作コードと従来Webカメラ出力です。iPhone版の統合は制作作業です。'
        '参照ソースには元キャラ専用の名前やハッシュ等が残るので、そのまま新キャラとして起動しません。\n\n'
        '初期化は1パーツだけです。新キャラ素材・切り抜き・リグ作成が必要です。'
        'ルナリスの編集用素材は含まず、完成版の再ビルド用一式ではありません。\n'
        '詳しくはinstructions/03_構成と技術引継ぎ.mdを読んでください。\n')
    sources = [
        'viewer/iphone-motion-v5.html', 'viewer/tracking-input-v5.js', 'viewer/iphone-motion-v4.js',
        'dist/tracking_webcam_legacy.js', 'dist/owl_prince_tracking_config_v5.json',
        'kamikan-bridge/src/bridge.js', 'kamikan-bridge/package.json', 'kamikan-bridge/package-lock.json',
        'kamikan-bridge/portable-motion-v5/server.js', 'kamikan-bridge/portable-motion-v5/run.js',
        'kamikan-bridge/portable-motion-v5/ui/index.html', 'kamikan-bridge/portable/起動.command',
        'tools/export_iphone_motion_v5.py', 'tools/package_iphone_motion_v5_mac.py',
        'docs/iphone-mouth-travel-v5.md', 'docs/iphone-mouth-travel-v5-values.json',
        'docs/iphone-pitch-gaze-v4.md', 'docs/iphone-motion-v3.md',
    ]
    for source in sources:
        copy('reference_sources/' + source, source)
    add('reference_sources/README.txt',
        'MOTION-5の読解用です。元リポジトリの相対パスと固有名が残るため、そのまま実行するプロジェクトではありません。\n'
        'runtime.js等の共通部はstarter、実行可能な見本はreferenceのZIPです。\n'
        '新キャラのrigを生成し、名前・保存先・版・SHA・書き出し処理を制作担当が統合してください。\n')
    archive_name = 'lunaris_iphone_motion_v5_mac.zip'
    copy('reference/' + archive_name, 'dist/' + archive_name)
    baseline_files = {name: {'sha256': sha256((ROOT / name).read_bytes()).hexdigest(),
                             'bytes': (ROOT / name).stat().st_size}
                      for name in ['dist/' + archive_name, 'dist/owl_prince_iphone_motion_v5.html',
                                   'dist/owl_prince.html']}
    checkpoint = {
        'saved_date': '2026-10-22', 'accepted_model': 'MOTION-5', 'reference_commit': BASELINE,
        'repository': '98nryk89/V', 'tag': 'owl-prince-motion5-baseline-2026-10-22',
        'user_feedback': '感度は十分。現状を保存し他キャラへ展開する。',
        'known_unresolved': ['実際に口を閉じていても、いの口になることがある。原因未確定。'],
        'model_modified_for_this_kit': False, 'files': baseline_files,
    }
    add('reference/checkpoint.json', json.dumps(checkpoint, ensure_ascii=False, indent=2) + '\n')
    manifest = {'reference_commit': BASELINE,
                'files': {name: {'bytes': len(data), 'sha256': sha256(data).hexdigest()}
                          for name, data in sorted(files.items())}}
    add('MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    output = ROOT / 'dist/codex_motion5_character_kit.zip'
    with ZipFile(output, 'w', ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(PREFIX + name, data)
    with ZipFile(output) as archive:
        assert archive.testzip() is None
        for name, info in manifest['files'].items():
            data = archive.read(PREFIX + name)
            assert len(data) == info['bytes'] and sha256(data).hexdigest() == info['sha256']
        assert archive.read(PREFIX + 'reference/' + archive_name) == (ROOT / 'dist' / archive_name).read_bytes()
    print(f'{output.name}: {output.stat().st_size:,} bytes; {len(files)} files; all hashes verified')


if __name__ == '__main__':
    main()
