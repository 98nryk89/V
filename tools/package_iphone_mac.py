"""Bundle the unchanged iPhone model, local setup GUI, vendored ws, and Mac launcher."""
from hashlib import sha256
from pathlib import Path
import json
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'dist/lunaris_iphone_mac.zip'


def main():
    files = {}
    for name in ['owl_prince_iphone_test.html', 'owl_prince_tracking_config.json', 'tracking_webcam_legacy.js']:
        files['html/' + name] = (ROOT / 'dist' / name).read_bytes()
    bridge = ROOT / 'kamikan-bridge'
    for name in ['src/bridge.js', 'portable/server.js', 'portable/run.js', 'portable/ui/index.html']:
        files['bridge/' + name] = (bridge / name).read_bytes()
    metadata = json.loads((bridge / 'package.json').read_text())
    metadata.update(name='lunaris-iphone-portable', version='1.0.0',
                    description='Lunaris HTML iPhone local launcher', scripts={'start': 'node portable/run.js'})
    files['bridge/package.json'] = (json.dumps(metadata, indent=2) + '\n').encode()
    ws = bridge / 'node_modules/ws'
    if not ws.is_dir() or json.loads((ws / 'package.json').read_text())['version'] != '8.22.0':
        raise RuntimeError('Run npm ci in kamikan-bridge before packaging (requires ws 8.22.0).')
    for path in sorted(ws.rglob('*')):
        if path.is_file():
            files['bridge/node_modules/ws/' + path.relative_to(ws).as_posix()] = path.read_bytes()
    files['起動.command'] = (bridge / 'portable/起動.command').read_bytes()
    files['使い方.html'] = (ROOT / 'docs/iphone-mac-start-guide.html').read_bytes()
    files['最初にお読みください.txt'] = ('''フクロウの王子｜Mac＋iPhone起動セット 1.0.0
2026年10月22日

1. 古いkamikan-bridgeが起動中なら終了します（旧ターミナルでControl＋C）。
2. このZIPを解凍し、Lunaris_iPhoneフォルダ内の「起動.command」をダブルクリック。
3. 自動で開くブラウザでiPhoneのIPを入力し「保存して接続」。
4. iPhoneのVTube Studioで顔追跡と「3rd Party PC Clients」をON、UDP21412。
5. 「モデル画面を開く」。正面・閉じ口でCキーを押して較正します。

詳しくは「使い方.html」を開いてください。OBSの手順も入っています。
npmの実行や設定JSONの編集は不要です。
黒いターミナル画面は自動で出ますが、入力せず利用中は閉じないでください。
終了はブラウザ接続画面の「中継を終了する」です。

必要：Mac、Google Chrome、iPhoneのVTube Studio、同じWi-Fi。
Node.js 22以上がMacに必要です（このZIPへNode本体は内蔵していません）。
以前npm startで中継を使えたMacでは通常インストール済みです。
初めての方は https://nodejs.org/ja/download のLTS版Macインストーラを使ってください。
Apple Silicon/Intelの各Macに入っているNodeを利用します。
wsライブラリはLICENSEと一緒に同梱済みなのでnpm installは不要です。

IPは自動保存され、次回から再入力不要です。IPが変わったときだけ画面で直します。
モデルは前回のiPhone試験版と同じで、絵や動きの新しい調整・軽量化はしていません。
笑顔は自動、驚きはiPhoneの2、真顔は3、自動へ戻すのは4。
Macのモデル画面でも1/2/0で表情操作できます。

htmlやbridgeフォルダをバラバラに移さず、フォルダ全体を保存してください。
''').encode('utf-8-sig')
    manifest = {'version': '1.0.0', 'date': '2026-10-22', 'nodeRequirement': '>=22 (not bundled)',
                'files': {name: sha256(data).hexdigest() for name, data in sorted(files.items())}}
    files['MANIFEST.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode()
    with ZipFile(ARCHIVE, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = ZipInfo('Lunaris_iPhone/' + name)
            info.create_system = 3
            info.compress_type = ZIP_DEFLATED
            info.external_attr = (0o100755 if name.endswith('.command') else 0o100644) << 16
            archive.writestr(info, data)
    with ZipFile(ARCHIVE) as archive:
        assert archive.testzip() is None
        assert (archive.getinfo('Lunaris_iPhone/起動.command').external_attr >> 16) & 0o111
        for name, digest in manifest['files'].items():
            assert sha256(archive.read('Lunaris_iPhone/' + name)).hexdigest() == digest
    print(f'{ARCHIVE.name}: {ARCHIVE.stat().st_size:,} bytes, {len(files)} files; launcher executable')


if __name__ == '__main__':
    main()
