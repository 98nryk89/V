"""HTML-only patch for the already approved Mac launcher. No executables."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = {
        'owl_prince_iphone_test.html': (ROOT / 'dist/owl_prince_iphone_v2.html').read_bytes(),
        'owl_prince_tracking_config_v2.json': (ROOT / 'dist/owl_prince_tracking_config_v2.json').read_bytes(),
        '更新手順.txt': '''iPhoneの回転・正面付近の安定化 v2 / 2026年10月22日

このZIPはHTMLと設定だけです。起動.commandや中継は取り替えません。

1. 今使っているLunaris_iPhoneフォルダをFinderで複製し、旧版のバックアップを残します。
2. このZIPの「owl_prince_iphone_test.html」と「owl_prince_tracking_config_v2.json」を
   今使っている「Lunaris_iPhone/html」の中へ入れます。HTMLは置き換えてください。
   htmlフォルダ全体の交換ではなく、中に2ファイルを入れるだけです。
3. すでに起動しているモデル画面をChromeで再読み込みします。
   未起動なら、今まで許可した同じ「起動.command」を開きます。
4. iPhoneを台などに固定し、正面・真顔・閉じ口で少し静止してCを押します。
   「正面・真顔を記録しました」が出ることを確認します。
5. 下を向く、左右を向く、元の正面へ戻す動きを試してください。

修正：VTube Studioの左右/上下軸の解釈、上下回転の向き、位置変化の過剰な増幅。
正面付近の微小な揺れを除外し、Cの基準は約0.3秒の複数フレームから記録します。
見た目の素材・髪・耳・口・笑顔・驚きの仕様は変更していません。
移動の感度は以前より落ち着く設定です。必要なら画面の感度で調整できます。

旧設定owl_prince_tracking_config.jsonやWebカメラ用JSは削除しないでください。
以前の状態へ戻すには、バックアップから元のHTMLを戻します。
新しい設定ファイルは元HTMLからは使われないので残っていても構いません。

まだ正面が大きくずれる場合は、モデル画面の「iPhone入力の確認」を開き、
正面で「診断値をコピー」を押して配布者に伝えてください。画像は含みません。
実機の生データ自体の変動まですべて解消できるとは限らないため、最終確認をお願いします。
'''.encode('utf-8-sig')}
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    files['MANIFEST.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode()
    output = ROOT / 'dist/lunaris_iphone_pose_v2_update.zip'
    with ZipFile(output, 'w', ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in files.items():
            archive.writestr('iPhone_v2_update/' + name, data)
    with ZipFile(output) as archive:
        assert archive.testzip() is None
        assert not any(name.endswith(('.command', '.js', '.exe')) for name in archive.namelist())
        for name, digest in manifest.items():
            assert hashlib.sha256(archive.read('iPhone_v2_update/' + name)).hexdigest() == digest
    print(f'{output.name}: {output.stat().st_size:,} bytes; HTML/config only, no launcher changes')


if __name__ == '__main__':
    main()
