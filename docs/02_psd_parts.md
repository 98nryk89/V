# 02. PSD パーツ分け仕様

`tools/check_psd.py` はこの仕様（`tools/parts_manifest.json`）に沿って検査します。

## 1. ファイル仕様

| 項目 | 値 |
|---|---|
| キャンバス | 腰上モデル: 4000×5000 前後 / 全身: 4000×8000 前後（長辺 4000px 以上） |
| カラー | RGB / 8bit |
| 背景 | 透明（白背景レイヤーは削除） |
| 保存先 | `art/psd/model.psd` |

### Cubism に取り込む前に処理しておくこと
- テキスト・シェイプ・スマートオブジェクト・調整レイヤー → **ラスタライズ**
- レイヤー効果（ドロップシャドウ等） → **ラスタライズ**（Cubism では無視される）
- レイヤーマスク → **適用**
- クリッピングした影・ハイライト → **下のレイヤーへ統合**（または Cubism 側でクリッピングを設定し直す）
- 乗算・スクリーン等の描画モード → Cubism 上で見た目が同じか確認
- 同じ名前のレイヤーを作らない

## 2. 命名ルール

- 半角英数字と `_`。Cubism のパーツ ID・アートメッシュ ID の元になるため。
- 左右は `_L` / `_R`。**キャラ本人から見た左右か、画面上の左右かをモデラーと最初に決め、全パーツで統一する**。
- 同じ種類の複数パーツは連番: `hair_front_1`, `hair_front_2`, …

## 3. レイヤー構成（上が手前）

太字は必須（`required`）、それ以外は品質を上げるための推奨パーツ（`recommended`）。

```
owl/                      フクロウ（肩の上 / 最前面寄り）
  owl_tuft_L, owl_tuft_R    耳羽
  owl_eyelid_L, owl_eyelid_R  閉じ目（描き足し）
  owl_eye_L, owl_eye_R
  owl_head
  owl_pendant               首のクリスタル
  owl_wing_L, owl_wing_R
  owl_body (+足)
head/
  ornament/
    ornament_crystal_1..n   仮面から垂れるクリスタル
    mask_ornament           仮面の髪飾り
    ribbon_1..n             紫リボン（物理用に分割）
  ahoge_1..n
  **hair_front_1..n**         前髪（毛束ごと。目にかかる束は独立）
  hair_shadow_on_face       前髪が顔に落とす影
  **brow_L, brow_R**
  eyes/
    **lash_upper_L / _R**     上まつ毛（線）
    lash_wing_L / _R        目尻のハネ
    **lash_lower_L / _R**
    **eyelid_closed_L / _R**  閉じ目の線（描き足し）
    **eye_highlight_L1.. / R1..**
    iris_shadow_L / _R      瞳上部の影
    **iris_L / iris_R**       瞳（隠れる部分も含めて全円で描く）
    eye_white_shadow_L / _R
    **eye_white_L / _R**      白目（まぶたの外まで少し広めに）
  mouth/
    **mouth_upper**           上唇の線
    **mouth_lower**           下唇の線
    **teeth_upper**
    **tongue**
    **mouth_inner**           口の中（描き足し）
  **nose**
  cheek_blush               照れ用（通常は非表示で使う）
  face_shadow_1..n          髪・あごの影
  **face**                  顔の肌（おでこまで描き足し）
  **ear_L, ear_R**
  earring_L_1..n / earring_R_1..n  耳飾り（クリスタル単位で分割）
  **hair_side_L1.. / hair_side_R1..**  横髪（顔の横〜胸）
hair_long_L_1..n / hair_long_R_1..n  体の前に垂れる銀髪の束
body/
  pocket_watch, chain_1..n
  crystal_1..n              胸・ケープの吊り飾り
  tassel_1..n               肩のタッセル
  cape_front_L, cape_front_R  肩〜胸のケープ（羽状部分は数枚に分割）
  **tie**, tie_crystal
  **collar**, choker
  belt, belt_strap
  **vest**                  ベスト（ボタン）
  **jacket_L / jacket_R**     ジャケット前身頃・襟
  arm_upper_L / _R, arm_lower_L / _R, sleeve_L / _R, hand_L / _R（手袋）
  **neck**, neck_shadow
cape_back                  背中側のケープ
**hair_back_1..n**           後ろ髪（全体のシルエット）
```

## 4. 描き足しが必要な箇所（チェックリスト）

- [ ] 前髪の下: おでこ、眉の全体、目の全体
- [ ] 目: 白目の全体、瞳の全円、閉じ目、笑い目用のまつ毛形状
- [ ] 口: 口の中、上の歯、舌、開いたときの下唇
- [ ] 顔の輪郭: 横を向いたときに見える頬・あごの外側
- [ ] 耳の後ろ、首の付け根（襟の中）
- [ ] 横髪・長い髪の内側（毛束が揺れたときに見える面）
- [ ] 銀髪の後ろにあるベスト・ジャケット（髪をどけた状態を描く）
- [ ] ケープ・タッセルの裏、肩の下の腕
- [ ] フクロウ: 閉じ目、羽を広げた状態（羽ばたき演出をするなら）
- [ ] 仮面の髪飾りの下の髪

## 5. 作業担当の選択肢

| 方法 | 内容 | 注意 |
|---|---|---|
| **外注（推奨）** | イラストレーターやパーツ分け専門の人に「清書＋パーツ分け＋描き足し」を依頼する | 本資料と `parts_manifest.json` を仕様書として渡せる |
| 自作 | AI アップスケール → 手作業でパーツ分けと描き足し | CLIP STUDIO / Photoshop 等で、まず顔だけ作って T1→T3 を先に通すと手戻りが少ない |

どちらの場合も、受け取った（作った）PSD で `python tools/check_psd.py art/psd/model.psd` を実行して T1 を通します。
