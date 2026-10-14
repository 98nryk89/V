# 03. Cubism モデリング仕様

使用ソフト: Live2D Cubism Editor 5.x（PRO 版。FREE 版は機能や規模に制限があり、この装飾量では足りない見込み）

## 0. 進め方の選択

| 方法 | 内容 |
|---|---|
| **外注（大手水準を確実に狙うなら推奨）** | Cubism のリガー（モデラー）に、`art/psd/model.psd`、この文書、`05_test_plan.md` の合格条件を渡して依頼する |
| 自作 | Cubism 5.0 の顔の動きの半自動生成と、5.1 のデフォーマ・揺れの自動生成で骨組みを作り、手で調整する |

**注意:** Cubism 5.3 で追加されたブレンドモードとオフスクリーン描画は、VTube Studio 側が対応しているかを T6 で確認するまで使わない。

## 1. 作業順序

1. PSD 読み込み → テクスチャアトラス作成（4096px、足りなければ 2 枚）
2. メッシュ分割（目・口・前髪は細かく、衣装は粗め）
3. デフォーマ構造（下記）を作る
4. **顔のパラメータ**: 目 → 口 → 眉 → 角度 X/Y/Z（ここで T3）
5. 体: 体の回転 X/Y/Z・呼吸・腕
6. 髪・装飾の揺れ用パラメータ → 物理演算（T4）
7. フクロウ
8. 表情 exp3 / 待機モーション
9. 組み込み用ファイル書き出し（moc3、cdi3「表示補助ファイル」を含める）→ T5

## 2. デフォーマ構造

```
全体の位置（ワープ）
└ 体の回転 Z（回転）
   └ 体の回転 X/Y（ワープ）
      ├ 呼吸（ワープ）
      ├ 腕 L/R（回転 → ワープ）
      ├ ケープ前 L/R（ワープ: 揺れ）
      ├ 長い髪 L/R（束ごとに 回転 ×3〜4 段: 物理）
      ├ フクロウ（体と一緒に動く → 内部で 頭/目/羽）
      └ 首（ワープ）
         └ 頭の回転 Z（回転）
            └ 顔の角度 X/Y（ワープ）
               ├ 目 L/R、眉 L/R、口（ワープ）
               ├ 前髪・横髪（束ごとの揺れ）
               ├ 髪飾り（仮面 + リボン揺れ + クリスタル振り子）
               └ 耳飾り L/R（振り子 3 段）
```

## 3. パラメータ

### 3.1 標準パラメータ（VTube Studio の初期設定が自動で割り当てる）

| ID | 範囲 | 内容 |
|---|---|---|
| ParamAngleX / Y / Z | -30〜30 | 顔の角度 |
| ParamEyeLOpen / ParamEyeROpen | 0〜1（〜1.2 で見開き） | 目の開閉 |
| ParamEyeLSmile / ParamEyeRSmile | 0〜1 | 笑い目 |
| ParamEyeBallX / Y | -1〜1 | 視線 |
| ParamBrowLY / RY, LX / RX, LAngle / RAngle, LForm / RForm | -1〜1 | 眉 |
| ParamMouthOpenY | 0〜1 | 口の開閉 |
| ParamMouthForm | -1〜1 | 口の形（への字〜笑顔） |
| ParamCheek | 0〜1 | 照れ |
| ParamBodyAngleX / Y / Z | -10〜10 | 体の回転 |
| ParamBreath | 0〜1 | 呼吸 |
| ParamHairFront / Side / Back | -1〜1 | 髪揺れ（物理の出力先） |

`tools/check_model.py` は上の表のうち、VTS が自動で割り当てる 15 個を必須、残りを推奨として検査します。

### 3.2 このキャラ用の追加パラメータ（案）

| ID | 用途 | 動かし方 |
|---|---|---|
| ParamHairLong_L1..4 / R1..4 | 長い銀髪の束（段ごと） | 物理 |
| ParamCapeL / ParamCapeR | ケープの揺れ | 物理 |
| ParamTassel | 肩のタッセル | 物理 |
| ParamEarringL1..3 / R1..3 | 耳飾り振り子 | 物理 |
| ParamOrnamentChain1..3 | 髪飾りのクリスタル | 物理 |
| ParamRibbon | 紫リボン | 物理 |
| ParamOwlEyeOpen | フクロウのまばたき | VTS の自動まばたき（目とずらす） |
| ParamOwlHeadX / ParamOwlHeadTilt | フクロウの首振り・首かしげ | 顔の角度に少し遅れて連動（物理） + ホットキー |
| ParamOwlWing | 羽ばたき | ホットキー（アニメーション） |
| ParamWatchOpen | 懐中時計の蓋（任意） | ホットキー |
| ParamCapeHem_L1..3 / R1..3 / Back1..3 | ケープの裾（全身） | 物理（大きく・ゆっくり） |
| ParamHemCrystal1..n | 裾のクリスタルの振り子 | 物理 |
| ParamSwayX | 全身の重心の左右移動（足は固定） | 体の角度 X と連動 |
| ParamTear / ParamShadowFace | 涙・顔の影（表情差分） | exp3 |

## 4. 物理演算グループ（目安）

先端ほど遅れて大きく揺れるよう、振り子は 3〜4 段に分けます。入力は基本的に「顔の角度 X / Z」と「体の角度 X / Z」の組み合わせです。

| グループ | 入力 | 出力 |
|---|---|---|
| 前髪 | AngleX, AngleZ | ParamHairFront |
| 横髪 | AngleX, AngleZ | ParamHairSide |
| 後ろ髪 | AngleX, AngleZ, BodyAngleX | ParamHairBack |
| 長い髪 L / R | AngleX, AngleZ, BodyAngleX | ParamHairLong_*1..4 |
| 耳飾り L / R | AngleX, AngleZ | ParamEarring*1..3 |
| 髪飾り（リボン + クリスタル） | AngleX, AngleZ | ParamRibbon, ParamOrnamentChain* |
| ケープ L / R | BodyAngleX, BodyAngleZ | ParamCapeL / R |
| タッセル | BodyAngleX, BodyAngleZ | ParamTassel |
| フクロウの首 | AngleX, BodyAngleX | ParamOwlHeadX |
| ケープの裾 L / R / 後ろ | BodyAngleX, BodyAngleZ, ParamSwayX | ParamCapeHem_* |
| 裾のクリスタル | BodyAngleX, BodyAngleZ | ParamHemCrystal* |

## 5. 表情（exp3）案

通常、笑顔（にっこり目）、照れ（頬）、驚き（見開き＋瞳小）、ジト目、怒り（眉）、涙。VTS のホットキーで切り替えます。
