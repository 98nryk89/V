"""HTML/config-only update. The already allowed Mac launcher is retained."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = {
        'owl_prince_iphone_test.html': (ROOT / 'dist/owl_prince_iphone_v21.html').read_bytes(),
        'owl_prince_tracking_config_v2.json': (ROOT / 'dist/owl_prince_tracking_config_v2.json').read_bytes(),
        '更新手順.txt': '''iPhone接続案内版 v2.1 / 2026年10月22日

今回確認された「接続中のまま」は、HTMLをfile:///で直接開いたことが原因でした。
HTMLをダブルクリックした画面からは、Macの中継がWebSocket接続を許可しません。
中継側の安全確認は変更していません。

【今すぐ開く方法：更新しなくても確認できます】
中継を起動したまま、Google Chromeのアドレス欄で
http://localhost:8765/
を開き、接続画面の「モデル画面を開く」を押してください。
HTMLファイル自体をダブルクリックしません。ターミナルへの入力は不要です。

【この更新版を使う場合】
1. 現在のLunaris_iPhoneフォルダを複製して、旧版を残します。
2. このZIP内のHTMLとJSONの2ファイルを、使用中のLunaris_iPhone/htmlへ入れます。
   HTMLは置き換え、htmlフォルダ全体は交換しません。
3. Chromeで上記URLの接続画面を開き、「モデル画面を開く」を押します。
   モデル画面を既に開いている場合は、http://から始まる方を再読み込みします。
4. 正面・閉じ口で少し静止し、Cで基準を記録します。

起動.command・Node・中継を取り替える必要はありません。
回転/位置の変換、デッドゾーン、表情、素材はv2のままです。

この版は、直接ファイルを開いた場合に接続画面へのリンクを表示します。
また、画面→中継の接続、中継→iPhoneデータ待ち、受信データの処理エラーを区別し、
接続待ちは5秒でタイムアウトさせて再試行します。中継の接続先も開いた画面に合わせます。

まだ止まる場合は、表示された接続状態とエラー文を伝えてください。
「iPhone入力の確認」→「診断値をコピー」でも確認できます。画像は含みません。
'''.encode('utf-8-sig')}
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    files['MANIFEST.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode()
    output = ROOT / 'dist/lunaris_iphone_connection_v21_update.zip'
    with ZipFile(output, 'w', ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in files.items():
            archive.writestr('iPhone_v21_update/' + name, data)
    with ZipFile(output) as archive:
        assert archive.testzip() is None
        for name, digest in manifest.items():
            assert hashlib.sha256(archive.read('iPhone_v21_update/' + name)).hexdigest() == digest
    print(f'{output.name}: {output.stat().st_size:,} bytes; HTML/config only')


if __name__ == '__main__':
    main()
