"""HTML/config-only update. The already allowed Mac launcher is retained."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = {
        'owl_prince_iphone_test.html': (ROOT / 'dist/owl_prince_iphone_v3.html').read_bytes(),
        'owl_prince_tracking_config_v3.json': (ROOT / 'dist/owl_prince_tracking_config_v3.json').read_bytes(),
        '更新手順.txt': '''iPhone動作設定版 v3

前版は上下/左右の軸を推測して交換したため、実機で方向が混線しました。
この版では固定の軸対応を使わず、実際の4姿勢から上下・左右・傾きを分離します。
診断値のコピー、JSON編集、ターミナル操作は不要です。

【更新】
1. 使用中のLunaris_iPhoneフォルダを複製し、旧版を保管します。
2. このZIPのHTMLとJSONを、使用中のLunaris_iPhone/htmlへ入れます。
   HTMLは置き換えます。htmlフォルダ全体や起動.commandは交換しません。
3. 中継を起動したまま、Chromeで http://localhost:8765/ を開き、
   「モデル画面を開く」を押します。画面にv3と出ることを確認してください。

【初回だけ：画面の案内に沿って4姿勢を記録】
iPhoneを固定し、各姿勢で0.3秒ほど静止して「記録」を押します。
スペースキーでも記録できます。
1 / 4 正面：正面を向いて口を閉じる。
2 / 4 下向き：首をかしげず、軽く下を向く。
3 / 4 右向き：正面に戻ってから、自分の右へ顔を向ける。かしげない。
4 / 4 かしげ：正面に戻り、正面を向いたまま頭を右肩へかしげる。
設定が済むまで回転と移動は固定し、誤った対応で動かしません。
3つの動きが似ていて区別できない場合は記録を進めず画面に案内を出します。
向きの設定はブラウザに保存します。以前のv2.2の向き設定は読み込みません。

【確認】
正面へ戻り、以下を別々に試してください。
・左右を向く → 顔の向き「左右」だけが動き、「上下」「傾き」は動かない。
・上下を向く → 顔の向き「上下」だけが動き、「左右」「傾き」は動かない。
・首をかしげる → 「傾き」だけが動く。
画面の上部に3つの現在値を表示しています。
次回は保存済み設定を読み込みます。正面だけを合わせ直す場合はCキー。
iPhoneの持ち方を変えるなどして向きが合わなくなった場合は
「動きの向きを合わせ直す」から再記録できます。

画像・パーツ・眉・髪・表情・回転範囲は維持しています。
旧版へ戻す場合は保管したフォルダを使用してください。
この版も実機の物理的な向きの最終確認は利用者の環境で必要です。
'''.encode('utf-8-sig')}
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    files['MANIFEST.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode()
    output = ROOT / 'dist/lunaris_iphone_motion_v3_update.zip'
    with ZipFile(output, 'w', ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in files.items():
            archive.writestr('iPhone_v3_update/' + name, data)
    with ZipFile(output) as archive:
        assert archive.testzip() is None
        for name, digest in manifest.items():
            assert hashlib.sha256(archive.read('iPhone_v3_update/' + name)).hexdigest() == digest
    print(f'{output.name}: {output.stat().st_size:,} bytes; HTML/config only')


if __name__ == '__main__':
    main()
