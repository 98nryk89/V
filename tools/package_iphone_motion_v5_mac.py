"""A complete version-checked bridge/model bundle; previous releases are preserved."""
import json
from pathlib import Path
from hashlib import sha256
from zipfile import ZipFile,ZipInfo,ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]

def main():
    files={}
    for name in ['owl_prince_iphone_motion_v5.html','owl_prince_tracking_config_v5.json','tracking_webcam_legacy.js']:
        files['html/'+name]=(ROOT/'dist'/name).read_bytes()
    files['html/owl_prince_iphone_test.html']=b'''<!doctype html><meta charset="utf-8"><title>MOTION-5</title><a href="http://localhost:8765/">MOTION-5 setup</a><script>if(location.protocol==='http:'||location.protocol==='https:')location.replace('./owl_prince_iphone_motion_v5.html'+location.search);</script>'''
    for name in ['server.js','run.js','ui/index.html']:
        files['bridge/portable/'+name]=(ROOT/'kamikan-bridge/portable-motion-v5'/name).read_bytes()
    files['bridge/portable/model-identity.json']=(json.dumps({'modelSha256':sha256(files['html/owl_prince_iphone_motion_v5.html']).hexdigest()})+'\n').encode()
    files['bridge/src/bridge.js']=(ROOT/'kamikan-bridge/src/bridge.js').read_bytes()
    metadata=json.loads((ROOT/'kamikan-bridge/package.json').read_text())
    metadata.update(name='lunaris-motion-verified',version='5.0.0',scripts={'start':'node portable/run.js'})
    files['bridge/package.json']=(json.dumps(metadata,indent=2)+'\n').encode()
    for path in sorted((ROOT/'kamikan-bridge/node_modules/ws').rglob('*')):
        if path.is_file():files['bridge/node_modules/ws/'+path.relative_to(ROOT/'kamikan-bridge/node_modules/ws').as_posix()]=path.read_bytes()
    files['起動.command']=(ROOT/'kamikan-bridge/portable/起動.command').read_bytes()
    files['使い方.txt']='''MOTION-5 起動確認付きセット

【今回の変更】
上向きに連動する黒目の移動をOFFにしました。黒目は顔と一緒に動きます。
横移動の最大幅は左右各90pxから135pxへ1.5倍に拡大。顔の回転範囲は同じです。
口は小さい動きから連続して開閉します。あ・い・えは一度に1種類だけ表示します。
閉じ口の基準を合わせるため、更新後は正面・閉じ口でCキーを押してください。
上下混入の抑制、瞬き、笑顔と驚きは前版のままです。
既存MOTION-3の有効な3方向設定は引き継ぎます。未設定の場合だけ初回記録します。

【すでに起動.commandを許可して使っている方】
1. 現在のLunaris_iPhoneフォルダを複製してバックアップします。
2. このZIP内の「html」「bridge」の2フォルダを、使用中のフォルダへコピーして置き換えます。
   起動.commandは今まで許可して使っていたものをそのまま残します。
3. 既存の起動.commandをダブルクリックします。
   別フォルダの旧中継が動いている場合は、このモデル用の中継だけを停止して新しい版へ切り替えます。
4. 新しく開いた接続画面の見出しが「MOTION-5」であることを確認します。
5. 「MOTION-5のモデル画面を開く」を押します。以前開いていたモデルのタブは閉じてください。

【初めて使う方】
ZIP全体を解凍し、起動.commandを開きます。Node.js 22以上が必要です。
未署名ファイルとしてmacOSの確認が必要になる場合があります。アプリの署名・公証済みではありません。

【モデルの初回設定】
画面で正面→下向き→右向き→右へのかしげを順番に記録します。
各姿勢で静止して記録ボタンまたはスペースキーを押します。
設定するまでは、推測した軸で動かさず顔の回転と移動を固定します。
設定はこのブラウザに保存します。Cは次回から正面だけを記録します。
左右・上下・傾きの現在値を画面に表示します。診断値を貼る操作は不要です。

このセットでは、起動フォルダ・モデルの内容が違う旧中継を誤って再利用しません。
中継とモデルの版が合わなければ追跡を開始せず、画面に案内を出します。
画像・パーツ・表情・回転範囲は従来通りです。
戻す場合は中継を終了し、バックアップした旧フォルダで起動してください。

iPhoneのVTube Studioは同じWi-Fi、3rd Party PC Clients ON、UDP21412です。
IPは以前の設定を読み込みます。変更時だけ接続画面から再設定してください。
ターミナルへの入力やnpm操作は不要です。
'''.encode('utf-8-sig')
    manifest={'version':'5.0.0','modelVersion':'MOTION-5','files':{name:sha256(data).hexdigest() for name,data in files.items()}}
    files['MANIFEST.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
    output=ROOT/'dist/lunaris_iphone_motion_v5_mac.zip'
    with ZipFile(output,'w',ZIP_DEFLATED,compresslevel=9) as archive:
        for name,data in sorted(files.items()):
            entry=ZipInfo('Lunaris_MOTION5/'+name);entry.create_system=3;entry.compress_type=ZIP_DEFLATED
            entry.external_attr=(0o100755 if name.endswith('.command') else 0o100644)<<16
            archive.writestr(entry,data)
    with ZipFile(output) as archive:
        assert archive.testzip() is None
        for name,digest in manifest['files'].items():assert sha256(archive.read('Lunaris_MOTION5/'+name)).hexdigest()==digest
    print(output.name,output.stat().st_size,'bytes')

if __name__=='__main__':main()
