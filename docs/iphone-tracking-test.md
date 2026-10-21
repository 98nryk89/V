# iPhone連携・別ファイルの試験版

現在の完成版 `dist/owl_prince.html` と `dist/owl_prince_artifact.html`、`viewer/index.html`、画像素材は変更していません。旧版は従来どおり利用できます。iPhone連携は新しい `dist/owl_prince_iphone_test.html` にのみ追加しました。

## Macで試す

1. 新版の次の3ファイルを、現在 `kamikan-bridge/config.json` の `htmlDir` で指定しているフォルダへ**一緒に**保存してください。初期設定ならリポジトリ内の `dist` です。
   - `owl_prince_iphone_test.html`
   - `owl_prince_tracking_config.json`
   - `tracking_webcam_legacy.js`（Webカメラに切り替えるときだけ必要）
2. 受信を確認できたiPhoneのVTube Studioを起動します。中継のiPhone IP設定は今までのものを使います。
3. `kamikan-bridge` フォルダで `npm start` を実行したままにします。
4. **MacのChromeのアドレス欄**へ、次のアドレスを入力します。HTMLのダブルクリックではなく、中継のHTTPから開いてください。

```text
http://localhost:8765/owl_prince_iphone_test.html
```

5. 初期入力はiPhoneです。表示が「iPhone追跡中」になったら、口を閉じて真顔・正面になり、**Cキー**または「正面・真顔を記録」を押してください。最初の顔も仮の基準にしますが、Cで合わせ直すと確実です。較正はページを閉じると消えます。
6. 顔の回転・上下左右移動、左右の瞬き、口「あ・い・え」、笑顔、iPhone画面のホットキー2を試してください。驚きは自動認識せず、**ホットキー2でON**になります。

Webカメラで同じ試験版を使う場合：

```text
http://localhost:8765/owl_prince_iphone_test.html?source=webcam
```

「開始」を押してChromeのカメラを許可します。入力プルダウンでも変更できます（ページ再読み込み）。`?source=iphone` の明示も可能です。iPhoneモードではカメラ用スクリプト・MediaPipe・WASM・顔認識モデルを取得せず、Webカメラの使用許可も要求しません。描画・呼吸・フクロウ・既存の物理はブラウザで引き続き動きます。

## 調整と表情

- 「滑らかさ (ms)」は0〜500。大きいほど揺れが減り、追従の遅れが増えます。初期値80。**瞬きと表情のON/OFFはぼかさず切り替えます。**
- 左右・上下・移動の感度と各方向の反転は操作パネルで調整できます。回転上限は左右・上・首かしげ5度、下10度を維持しています。
- 笑顔は両側の強い笑顔スコアが0.80超で約0.45秒続いたときON、0.55未満が約0.35秒続くと解除します。
- Chromeの数字1は笑顔、2は驚きのON/OFF、0は真顔。表情ボタンも維持しています。手動指定が自動笑顔より優先し、両表情を重ねません。「自動判定に戻す」か笑顔の自動判定チェックをONにすると自動へ戻ります。
- iPhoneのホットキーは**ON/真顔などの命令**です。同じ番号が毎フレーム来ても繰り返し反転しません。初期割り当ては1=笑顔ON、2=驚きON、3=真顔、4=自動笑顔へ戻す、5〜8=何もしない。
- 顔を見失った場合・最後の受信から750ms経った場合は、口を閉じ、目を開き、正面・真顔へゆっくり戻ります。中継が止まってもブラウザは毎秒再接続し、中継自体も既存の毎秒要求を続けます。顔が復帰すると手動で指定していた表情も再び反映します。
- 停止ボタンは入力を停止して現在の姿勢を保持します。Cは**新しい顔データを検出できているときだけ**受け付けます。

設定を次回も使うには `owl_prince_tracking_config.json` を変更してページを再読み込みします。パネルの操作はそのページ内だけです。中継用の `kamikan-bridge/config.json` とは別の設定です。

```json
{
  "wsUrl": "ws://localhost:8765",
  "smoothingMs": 80,
  "lostReturnMs": 500,
  "staleMs": 750,
  "gainX": 1,
  "gainY": 1,
  "gainMove": 1,
  "positionScale": 10,
  "invX": false,
  "invY": false,
  "invZ": false,
  "hotkeys": {
    "1": "smile", "2": "surprise", "3": "neutral", "4": "auto",
    "5": "none", "6": "none", "7": "none", "8": "none"
  }
}
```

`hotkeys` の1〜8に `smile` / `surprise` / `neutral` / `auto` / `none` を指定できます。`positionScale` はiPhoneの位置の差をモデルの体移動へ変える倍率です。位置の単位・向きは実機で確認し、動きすぎる場合は「移動の感度」やこの値を下げてください。頭の回転と体の位置移動は独立しています。

## 対応付けと制限

| iOSデータ | 試験版での反映 |
|---|---|
| Rotation.y / x / z | 基準からの角度差 → AngleX / Y / Z。初期符号は - / - / +、度単位、反転設定可 |
| Position.x / y | 基準からの差 × positionScale × gainMove → BodyX/Y（-1〜1）。奥行きは使わない |
| EyeBlinkLeft/Right | 0.15〜0.65を各EyeOpenの1〜0へ変換。左右独立、追加スムージングなし |
| JawOpen / MouthStretchLeft/Right | 基準の顎開きとの差と横への伸びでMouthOpen(0〜1)、MouthForm(0:A / 1:I / 2:E)を決定 |
| MouthSmileLeft/Right | 両側スコアと保持時間 → 自動Smile。手動指定中は反映しない |
| EyeWideLeft/Right | 自動の驚きには使わない。ホットキー2でSurpriseを指定 |
| Hotkey | 設定表から既存の表情操作へ。未知番号は無視 |
| FaceFound | falseなら滑らかに正面・真顔へ戻す |

ARKitのブレンドシェイプは母音の正解ラベルではありません。顎開きが大きいとA、横に広く小さめの開きならI、ほどよい開きと横伸びならEという**近似判定**です。50msの候補保持後に形を切り替え、形そのものは混ぜません。小さい口の動きを無視するデッドゾーンを維持します。Iのような横長の口も検出するため横伸びでも開き始めます。

眉は引き続き肌と一体で、独立した眉追従はしません。画像・rig・メッシュ・描画ランタイムは旧版と同じです。眼球回転、独立した眉、舌、頬、U/O、奥行き移動など、現在のモデルにない動きは追加していません。黒目は従来どおり頭・体の動きに少し追従します。髪の独立した揺れも再開していません。

Webカメラ選択時は既存のMediaPipe処理を外部ファイルとして読み込みます。旧処理の口の平滑化はそのまま残り、新しい共通スムージングをさらに加えます。Webカメラのデフォルトも自動笑顔・手動の驚きです。従来版HTMLの自動驚きなどの設定は変更していません。

## 開発・検証・戻し方

- 共通入力・iPhone変換・WebSocket再接続・Webカメラ遅延読み込み：`viewer/tracking-input.js`。
- 試験版のUI：`viewer/iphone-test.html`。
- 再出力：ルートで `python tools/export_iphone_test.py`。完成版HTMLの**埋め込みrigをそのままコピー**し、試験版だけを出力します。画像のbuildや切り抜きは不要です。既存の試験版設定JSONは上書きしません。
- 単体検証：`node --test tests/tracking_input.test.cjs tests/tracking.test.cjs`（新12件＋既存19件）。
- 中継検証：`cd kamikan-bridge && npm test`（9件）。
- Chromium検証：ルートで `python -m unittest tests/test_iphone_input_browser.py -v`（3件）。Playwright・Chromium・中継のnpm依存が必要です。ループバックの模擬iPhoneをUDP→中継→実WebSocket→配布HTMLへ接続し、Webカメラの遅延起動・停止、5姿勢で旧版との描画一致も確認します。Webカメラ認識器だけは模擬値です。
- 画像は `/workspace/iphone-integration-check/iphone-test.png` に試験時の表示を保存し目視確認。旧HTML3ファイルと全既存画像のハッシュも照合しています。
- **戻すには旧版 `http://localhost:8765/owl_prince.html` を開くだけ**です。ファイルの上書きやrevertは不要です。試験追加全体も単一コミットでrevertできます。

実iPhoneから中継までの受信は利用者が確認済みです。今回のHTMLとの最終的な感度・方向・母音判定と、実Webカメラ・OBSでの仕上がりは利用者のMacで確認してください。
