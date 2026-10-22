"""HTML/config-only update. The already allowed Mac launcher is retained."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = {
        'owl_prince_iphone_test.html': (ROOT / 'dist/owl_prince_iphone_v22.html').read_bytes(),
        'owl_prince_tracking_config_v22.json': (ROOT / 'dist/owl_prince_tracking_config_v22.json').read_bytes(),
        '更新手順.txt': '''iPhone上下回転修正版 v2.2

【変更点】
前版の固定の軸対応では、実機で横向きがうつむきに混ざりました。
上下と左右を入れ替え、下向きの符号も修正しました。
初期設定: Rotation.x → 上下、Rotation.y → 左右、Rotation.z → 首のかしげ。
横移動・縦移動・首のかしげは、うつむきへ加算しません。
軽く下を向いた段階から反映し、上5度・下10度・左右5度の範囲を維持します。

【更新方法】
1. 現在のLunaris_iPhoneフォルダを複製して旧版を保管します。
2. このZIPのHTMLとJSONの2ファイルを、使用中のLunaris_iPhone/html/へ入れます。
   HTMLは置き換えます。htmlフォルダ全体は置き換えません。
3. 中継を起動し、Chromeで http://localhost:8765/ を開きます。
4. 「モデル画面を開く」を押し、画面にv2.2と表示されることを確認します。
   開いていたモデル画面は再読み込みしてください。HTMLを直接ダブルクリックしません。
5. iPhoneを固定し、正面・閉じ口で少し静止してCキーを押します。
6. 下を向く・横を向く・首をかしげる動きを別々に確認します。

【まだ下向きが合わない場合】
受信値の向きを推測し続けないよう、実際の下向きで合わせる機能も付けました。
画面の「下向きが合わない場合」を開きます。
① 正面でCキーを押します。
② 横を向かず、軽く下を向いて0.3秒ほど静止したまま、
   「この姿勢を『下向き』として合わせる」を押します。
設定はこのブラウザに保存されます。Cによる正面の再記録でも保持します。
首をかしげた姿勢や上下左右が混ざった姿勢では記録せず、再試行を案内します。
実機の動きがないと物理的な方向は断定できないため、この調整を用意しています。

起動.command・中継・Nodeを交換する必要はありません。
画像・パーツ・眉・耳・髪・表情・Webカメラ版は変更していません。
旧版へ戻す場合は、保管した旧フォルダで起動してください。
'''.encode('utf-8-sig')}
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    files['MANIFEST.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode()
    output = ROOT / 'dist/lunaris_iphone_pitch_v22_update.zip'
    with ZipFile(output, 'w', ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in files.items():
            archive.writestr('iPhone_v22_update/' + name, data)
    with ZipFile(output) as archive:
        assert archive.testzip() is None
        for name, digest in manifest.items():
            assert hashlib.sha256(archive.read('iPhone_v22_update/' + name)).hexdigest() == digest
    print(f'{output.name}: {output.stat().st_size:,} bytes; HTML/config only')


if __name__ == '__main__':
    main()
