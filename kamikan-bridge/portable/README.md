# フクロウの王子：Macのダブルクリック起動セット

アプリ化せず、iPhone VTube Studio → Node中継 → 既存HTML → OBSを使う配布セットです。
`dist/lunaris_iphone_mac.zip` を解凍して `起動.command` を開き、ブラウザでiPhoneのIPv4を保存します。
旧HTML・画像素材は変更せず、iPhone試験HTMLをそのまま同梱します。Webカメラ用JSも同梱しますが、iPhoneモードでは読み込みません。

利用者は `npm start` / `npm ci` / JSON編集を行いません。Node.jsは内蔵していないので初回だけNode.js 22以上のLTS版を公式のMacインストーラで導入します。
以前の中継を使えたPCでは通常導入済みです。Apple Silicon/Intelの両方で、各Macにインストール済みのNodeを使います。
`.command` でターミナルは開きますが、入力は不要です。Macでの実際のダブルクリック・初回許可は利用者PCで確認が必要です。

## 原本と再生成

- `portable/server.js`: localhost設定API、保存、既存中継の再利用。
- `portable/run.js`: 起動、同じモデルの二重起動を検知、Chromeを開く。
- `portable/ui/index.html`: IP入力、状態、モデル表示、終了ボタン。
- `portable/起動.command`: Mac用起動ファイル。
- `tools/package_iphone_mac.py`: 旧HTML、上記ファイル、ws依存（LICENSE含む）、説明書をZIP化。
- `docs/iphone-mac-start-guide.html`: 利用者向けの説明書。

`node_modules/ws` がなければ、制作者が `kamikan-bridge` で `npm ci` を行ってから、ルートで `python tools/package_iphone_mac.py` を実行します。
ws 8.22.0のみを同梱し、npmキャッシュや開発用テストは配布しません。

## 状態と保存

HTTP/WSはlocalhost:8765、UDP受信11125、iPhone要求21412。IP未設定の初回は通信要求を送らず設定画面だけ起動します。
入力を保存すると、同じ受信ソケットを保ったまま新IPへ要求し、毎秒の再要求と接続断後の復帰を継続します。
IP変更時は旧状態を消し、旧IPからのデータは受け付けません。WebSocket原文と未知フィールドは変更しません。

MacのIP保存先は `~/Library/Application Support/KamikanBridge/owl-prince/connection.json`。
ZIP内のJSONを利用者が書き換える必要はありません。更新版へフォルダを置き換えても同じMacユーザーの設定は残ります。
設定操作は同じOriginのJSON POSTだけを受け付け、外部サイトから変更・終了できないようにしています。
設定・ソースのフォルダはHTTPで配信せず、htmlフォルダだけをモデル表示に使います。

## 検証

`kamikan-bridge` で `npm test`。新しい設定API/保存/再開/生UDP転送/終了と旧中継の回帰を検証します。
配布ZIPを解凍したNodeから起動する検証では、`KAMIKAN_HTML_DIR` と `KAMIKAN_SETTINGS_FILE` の一時パスを使えます。
`KAMIKAN_NO_OPEN=1` はクラウドでブラウザを自動起動しないための検証用です。
クラウド内はループバック模擬iPhoneを使用し、利用者のLANへ接続できたとは主張しません。

現段階は初回のIP入力が必要です。自動検出・Node内蔵・署名/公証・透明OBS専用ウィンドウ・新たな描画軽量化は実装していません。
