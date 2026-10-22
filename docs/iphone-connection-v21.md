# iPhone接続案内版 v2.1

利用者が確認した停止画面のURLは `file:///` だった。配布中継はWebSocketのOriginをローカルHTTP画面に限定し、ファイルを直接開いた `null` Originを拒否する。VTube Studio側の「サードパーティーPCクライアントに接続」は、HTMLとの接続完了を意味しない。

## 既存版での開き方

中継を起動したまま、Chromeで `http://localhost:8765/` を開き、接続画面の「モデル画面を開く」を押す。HTMLをダブルクリックしない。更新・ターミナル操作は不要。

## 任意のHTML更新

`dist/lunaris_iphone_connection_v21_update.zip` のHTML/JSONを、バックアップした既存の `Lunaris_iPhone/html/` へ追加・置換する。フォルダ全体を交換しない。起動ファイル・中継・Nodeは交換しない。

- `viewer/tracking-input-v21.js` / `viewer/iphone-v21.html` を追加し、旧v2を保護。
- 直接ファイルを開いた場合はWebSocketを試行せず、接続画面へのリンクを表示。
- 標準のローカル接続先は開いたHTTP画面のポートに合わせ、IPv4待受へ接続。明示した別ポート・パスは維持。
- 接続開始から5秒で打ち切って再試行。開通後のiPhoneデータ待ち、顔未検出、JSON/反映エラーを表示で区別。停止・再接続前の古いイベントを無視。
- 任意の状態APIから中継の受信fpsを確認。API非対応でも追跡を続行。
- 受信のコピーで `structuredClone` / Array.atを必須にしない。今回の利用者側の原因がこれらだったと確認したわけではない。

再生成: `python tools/export_iphone_connection_v21.py`、`python tools/package_iphone_connection_v21_update.py`。ZIPはHTML・既存v2設定・日本語手順・ハッシュ一覧だけを含む。旧v2更新ZIPと旧完成版HTMLは保持する。

## 検証

Nodeの関連55件、ブラウザ3件が成功。既存Mac配布ZIPに2ファイルだけを適用し、設定のWebSocket URLをテストで差し替えることなく接続・受信・較正・回転・表情を確認。5姿勢で完成Webカメラ版と描画ハッシュが一致。下向き・左右・正面の画像も確認。

管理下Chromiumでは実ファイルURLの閲覧が禁止されているため、その制限を回避していない。file URLの拒否はNodeの仮想環境で確認し、同じ案内のブラウザ表示はabout:blankへのHTML読み込みで確認。実Macのファイル起動と実iPhoneは利用者側の再確認が必要。
