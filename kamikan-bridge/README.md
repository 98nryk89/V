# KamikanBridge：iPhoneのVTube Studio → ブラウザ中継

iPhoneへ1秒ごとに追跡データを要求し、UDPで受けたJSONをローカルWebSocketへ転送するNode.jsサーバーです。同じサーバーから既存HTMLも配信します。

**この段階では既存HTML・モデルの処理は変更していません。HTMLを開くだけではiPhone追従へ切り替わりません。今回できるのはデータの受信・中継とHTML配信までです。**

## 1．初回だけの準備（Mac）

1. [Node.js公式サイト](https://nodejs.org/)からLTS版をインストールします。Node.js 22以上が必要です。
2. この `kamikan-bridge` フォルダをMacに保存します。リポジトリ全体を保存した場合は、その中の同名フォルダを使います。
3. ターミナルを開き、`cd `（末尾に半角スペース）を入力し、Finderの `kamikan-bridge` フォルダをターミナルへドラッグしてReturnを押します。
4. 次を実行します。

```sh
npm ci
```

依存ライブラリはWebSocket用の `ws` のみです。PythonやVTube StudioのPC版は不要です。

## 2．iPhone側を設定する

1. MacとiPhoneを同じWi-Fi／相互通信できるLANにつなぎます。ゲストWi-Fiでは端末間通信が遮断される場合があります。
2. iPhoneで **VTube Studio** を開きます。
3. 最初の設定タブの下部にある **「3rd Party PC Clients」** をオンにします。アプリに表示されるUDP要求先ポートは **21412** にしてください。
4. 顔トラッキングを動かし、アプリを前面に表示したままにします。
5. iPhoneの「設定 → Wi-Fi → 接続中のネットワークの ⓘ → IPアドレス」を確認します。**MacのIPではなく、iPhoneのIPv4アドレス**です。
6. iPhoneでローカルネットワークへのアクセス許可を求められたら、VTube Studioに許可します。

## 3．config.jsonを編集する

```json
{
  "iphoneIp": "192.168.1.100",
  "htmlDir": "../dist"
}
```

- `iphoneIp`：例の値を、ご自身のiPhoneのIPに置き換えます。
- `htmlDir`：配信するHTMLが入ったフォルダです。**config.jsonのある場所を基準**に解決します。絶対パスも指定できます。

リポジトリ全体を保存している場合、初期値 `../dist` で既存の完成HTMLを配信できます。このフォルダだけを保存した場合は、例えば `html` フォルダを作り、完成HTMLをコピーして `"htmlDir": "./html"` にしてください。サーバーはHTMLを書き換えません。

Macのフォルダ指定例：`"htmlDir": "/Users/ユーザー名/Desktop/VTuber"`。テキストエディタでは標準テキストとして保存し、JSONの半角ダブルクォートを使ってください。

## 4．起動する

`kamikan-bridge` フォルダで次を実行するだけです。

```sh
npm start
```

起動後、Chromeで次を開きます。

```text
http://localhost:8765/
```

`htmlDir` に `index.html` があればそれを表示し、なければフォルダ直下のHTMLへのリンクを表示します。既存モデルは初期設定なら `http://localhost:8765/owl_prince.html` です。`owl_prince_artifact.html` はカメラUIを除いた別用途のファイルです。

**ターミナルは起動したままにしてください。** 終了はターミナルで **Control＋C**。設定を書き換えた場合は、いったん終了して `npm start` し直します。要求が止まると、iPhoneの送信も最大約5秒後に止まります。

## 5．受信の見方

1秒ごとに次のようなログを表示します。

```text
受信fps=59.9 FaceFound=true eyeBlinkLeft=0.375 jawOpen=0.625
```

| 表示 | 意味 |
|---|---|
| 受信fps | 直近の測定区間で受けた、有効なJSONの秒間件数。通常は約60ですが端末・環境で変動します |
| FaceFound=true / false | iPhoneが顔を検出している／していない |
| eyeBlinkLeft | 左目を閉じる値。通常0〜1 |
| jawOpen | 顎を開く値。通常0〜1 |
| `fps=0.0` と `--` | データ待ち。古い顔の値は表示せず、再要求を継続中 |

公式の `BlendShapes` 配列の `EyeBlinkLeft`・`JawOpen` を読みます。項目名の大文字・小文字の違いも受け付けます。欠けた値は `--` と表示します。壊れたJSONは無視して件数を表示し、その後の正常データは引き続き受信します。

## データの流れとWebSocket形式

```text
Mac → iPhoneのUDP 21412：起動直後と、以降1秒ごとに要求
iPhone → MacのUDP 11125：約60fpsのJSON
Mac → ws://localhost:8765：接続中のブラウザへテキストJSONを転送
Mac → http://localhost:8765/：指定フォルダのファイルを読み取り専用で配信
```

要求は次のとおりです。

```json
{"messageType":"iOSTrackingDataRequest","time":5,"sentBy":"KamikanBridge","ports":[11125]}
```

WebSocketには、受信したJSONオブジェクトを包み直さず送ります。`Timestamp`、`FaceFound`、`Hotkey`、`Rotation`、`Position`、`EyeLeft`、`EyeRight`、52個の `BlendShapes: [{"k":"EyeBlinkLeft","v":0.1}, ...]` をそのまま保持します。未知の項目も削除しません。`FaceFound=false` のフレームも転送します。

接続後からの新しいフレームを配信し、過去フレームは再送しません。通信断時に架空の顔データも作りません。将来HTMLへ接続するときは、ブラウザ側でタイムアウトとWebSocketの再接続を扱ってください。遅いクライアントへの送信待ちが増えた場合は、古いフレームを蓄積せず、そのクライアントへの転送を一時的に間引きます。

**開発者向け・任意のブラウザ確認：** ターミナルの受信ログだけでもiPhoneとの通信を確認できます。ブラウザへの転送まで確認する場合は、上のHTTPページをChromeで開き、開発者ツールの「Console」で次を実行します。新しく届くデータだけが表示されます。

```js
var vtsSocket = new WebSocket('ws://localhost:8765');
var vtsNextLog = 0;
vtsSocket.onmessage = event => {
  if (Date.now() >= vtsNextLog) {
    console.log(JSON.parse(event.data));
    vtsNextLog = Date.now() + 1000;
  }
};
// 確認終了時：vtsSocket.close();
```

HTTPとWebSocketはMac内だけで使う設定です。ブラウザからは、このサーバーで配信した `http://localhost:8765` のページを使ってください。別サイトや `file://` からのWebSocket接続は受け付けません。UDPはLANから受信し、設定したiPhoneの送信元IPだけを受け付けます。

## つながらない場合

| 症状 | 確認すること |
|---|---|
| 起動直後からfpsが0 | iPhoneのIP、同じLAN、3rd Party PC Clients、iPhone側21412番、アプリが前面にあるか |
| Macのネットワーク許可が表示される | Node.js／ターミナルなど起動元アプリにローカルネットワーク通信を許可する。macOSのファイアウォールでNode.jsの受信を許可する |
| Wi-Fi切断後にfpsが0 | 復旧を待つ。要求は自動継続する。iPhoneのIPが変わった場合だけconfig.jsonを更新して再起動する |
| FaceFound=falseが続く | 通信はできている。iPhone側の顔認識・明るさ・カメラ方向を確認する |
| EADDRINUSE | UDP 11125またはTCP 8765を別プロセスが使用中。二重起動した中継などを終了する |
| HTMLフォルダが見つからない | htmlDirの場所とフォルダの存在を確認する。Mac内で実在するパスを指定する |
| HTMLは出るがキャラがiPhoneで動かない | 今回は中継のみ。モデル側のWebSocket受信・パラメータ変換は未実装 |

## 検証と公式資料

```sh
npm test
```

模擬iPhoneによるUDP要求・複数WebSocketへの原文転送・52項目と未知フィールドの保持・ログ表示・通信断からの再開・HTTP配信などを検証します。実iPhone／macOSでの通信は利用者の環境で最終確認してください。

- [公式プロトコル説明](https://github.com/DenchiSoft/VTubeStudioBlendshapeUDPReceiverTest)
- [公式受信JSON定義](https://github.com/DenchiSoft/VTubeStudioBlendshapeUDPReceiverTest/blob/main/Assets/VTubeStudioBlendshapeDataReceiver/VTubeStudioRawTrackingData.cs)
- [公式ブレンドシェイプ名](https://github.com/DenchiSoft/VTubeStudioBlendshapeUDPReceiverTest/blob/main/Assets/VTubeStudioBlendshapeDataReceiver/VTSARKitBlendshape.cs)
