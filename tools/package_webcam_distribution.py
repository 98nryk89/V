"""Package the approved webcam HTML unchanged, with recipient-facing Japanese docs."""
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'dist/owl_prince.html'
ARCHIVE = ROOT / 'dist/lunaris_webcam_distribution.zip'


def main():
    model = MODEL.read_bytes()
    instructions = (ROOT / 'docs/webcam-user-guide.html').read_bytes()
    readme = '''ルナリス HTML＋Webカメラ版（2026年10月21日）

【最初の起動】
1. このZIPを解凍します。
2. owl_prince.html を右クリック →「このアプリケーションで開く」→ Google Chrome。
3. 右側「Webカメラ追跡 (MediaPipe)」の「開始」を押し、カメラを許可します。
4. 正面・真顔・閉じ口で「正面を較正」を押します。

詳しい操作、Macのカメラ許可、OBSへの取り込み、困ったときの対処は
同じフォルダの「操作説明.html」をダブルクリックしてお読みください。

必要：PC、Google Chrome、Webカメラ、インターネット接続。
不要：iPhone、VTube Studio、Node.js、npm、中継サーバーの設定。

キャラクター画像はHTMLに入っています。
顔認識用のライブラリ・モデルはカメラ開始時にネットから読み込みます。
完全オフライン版ではありません。

1=笑顔、2=驚き、0=真顔。各ボタンでも操作できます。
自動の笑顔・驚きは初期ONです。不要なチェックは外してください。
手動で表情を指定すると自動判定は停止します。
設定は再読み込みで初期状態に戻ります。

この配布物は既存のWebカメラ完成版そのものです。
iPhone試験版や新しい軽量化版ではありません。まず使用するPCでお試しください。
配信時はChromeを起動したままOBSへ画面を取り込みます。

【配布者向け】
このZIPをそのままメンバーへ渡せます。元画像・開発環境は不要です。
HTML・画像の変更はしていません。制作・再配布の利用範囲は配布者の案内に従ってください。
'''
    with ZipFile(ARCHIVE, 'w', ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in [
            ('owl_prince.html', model),
            ('はじめに.txt', readme.encode('utf-8-sig')),
            ('操作説明.html', instructions),
            ('VERSION.txt', ('Webcam model SHA256: ' + sha256(model).hexdigest() + '\n').encode()),
        ]:
            archive.writestr('Lunaris_Webcam/' + name, content)
    with ZipFile(ARCHIVE) as archive:
        assert archive.testzip() is None
        assert archive.read('Lunaris_Webcam/owl_prince.html') == model
        assert len(archive.namelist()) == 4
    print(f'{ARCHIVE.name}: {ARCHIVE.stat().st_size:,} bytes; model SHA256 {sha256(model).hexdigest()}')


if __name__ == '__main__':
    main()
