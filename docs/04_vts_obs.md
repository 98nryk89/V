# 04. VTube Studio と OBS の設定

## 1. 必要なもの

| 種類 | 内容 | 備考 |
|---|---|---|
| ソフト | Live2D Cubism Editor 5.x（PRO） | モデリング |
| ソフト | VTube Studio（Steam 版、PC） | トラッキング |
| ソフト | OBS Studio | 配信 |
| トラッキング機材 | **iPhone（Face ID 搭載機）＋ VTube Studio アプリ（推奨）** | 口の形・頬・眉の細かい動きを拾えるのは ARKit。参考モデルの水準を目指すなら事実上必須 |
| 〃（代替） | Web カメラ | 動作確認用。口の形・眉の精度は下がる |
| 配信 PC | VTS と OBS を同時に動かせる GPU | T9 で負荷を確認する |
| 素材制作 | Photoshop / CLIP STUDIO PAINT など | PSD 作成 |

## 2. VTube Studio

### 2.1 モデルの読み込み
1. VTS → 設定 → 「モデルフォルダを開く」で `Live2DModels` を開く
2. 書き出したフォルダ（`*.model3.json` が入ったもの）をそのままコピー
3. VTS のモデル選択から読み込み → `*.vtube.json` が生成される（以後これも `model/runtime/` に保存）

### 2.2 トラッキング
- iPhone: 同じネットワークに接続し、PC 側の「iPhone/Android から接続」を有効にする。アプリ側で PC の IP を入力
- 起動したら必ず「キャリブレーション」（正面・無表情）

### 2.3 パラメータ割り当て（標準外の追加分）

| VTS 入力 | 出力パラメータ | メモ |
|---|---|---|
| FaceAngleX / Y / Z | ParamAngleX / Y / Z | 初期設定のまま |
| FaceAngleX × 0.3 程度 | ParamBodyAngleX | 体を少し遅れて追従させる |
| EyeOpenLeft / Right | ParamEyeLOpen / ROpen | 閉じきりの閾値を調整 |
| MouthSmile | ParamMouthForm, ParamEyeLSmile / RSmile | 笑顔で目も細める |
| MouthOpen | ParamMouthOpenY | 音声リップシンクと併用可 |
| Brows | ParamBrowLY / RY | iPhone なら左右別に割り当てる |
| CheekPuff | ParamCheek | 任意 |
| （自動まばたき） | ParamOwlEyeOpen | フクロウ用。周期を本人と変える |

### 2.4 ホットキー
- 表情（exp3）: 笑顔 / 照れ / 驚き / ジト目 / 怒り / 涙
- 演出: フクロウ羽ばたき、懐中時計の蓋
- 「物理演算」の設定でモデル全体の揺れの強さ・風を調整

## 3. OBS

### 3.1 映像の取り込み（どちらか）
| 方法 | 設定 | 特徴 |
|---|---|---|
| **ゲームキャプチャ（推奨）** | ソース「ゲームキャプチャ」→ 特定のウィンドウ = VTube Studio、**「透過を許可」にチェック** | 追加プラグイン不要。VTS 側の背景は何でもよい |
| Spout2 | VTS 設定で Spout2 出力を有効 → OBS に Spout2 プラグインを入れてソース追加 | VTS のウィンドウサイズに依存しない |

### 3.2 確認すること
- 髪の毛先・クリスタルの縁に白/黒のフチが出ていないか（透過の確認）
- VTS のフレームレート上限を配信と揃える（60fps 配信なら 60）
- OBS の「統計」でレンダリングラグ・エンコードラグが出ていないか
