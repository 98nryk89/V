# AGENTS.md — live2d_ai(Codex / 他のエージェント向けの引き継ぎ)

1枚のイラストから、**元絵の画素を切り出して動かす**(Live2D 風)モデルを作るツールと、そのサンプル(`projects/owl_prince`)。
詳細な作法・失敗の記録は **`CLAUDE.md` に全部ある**(必読。このファイルは入口と並行作業の決まり)。

## 最重要の方針
1. **動く部分を AI で再生成しない。** 元絵の画素をそのまま切り出して変形する(再生成は元絵と少し違ってしまうため、ユーザーが嫌がっている)。生成してよいのは、元絵に存在しない画素(閉じ目の線、口の中、隠れた部分)だけ。
2. ユーザーが渡した**参考絵(お手本)の画素は、そのまま使う**(`samples/` に保存。まばたき、母音の口、笑顔、下向きの耳)。
3. **確認せずに「直った」と言わない。** パーツを1つずつ隠して原因を絞り、参考絵と同じ高さで並べて、画像を目視する。直せないなら理由を説明する。
4. 悪化したら、ユーザーは「戻して」と言う。**1回の変更を小さく、1コミット1目的にする**(`git revert` で戻せるように)。
5. ユーザーの言葉は日本語。報告は日本語、短く、事実のみ。

## 環境
```sh
tools/setup.sh                      # numpy scipy opencv-python-headless pillow playwright
python -m live2d_ai build projects/owl_prince      # → projects/owl_prince/out/(rig.json + parts/*.png)
python -m live2d_ai export projects/owl_prince -o dist/owl_prince.html   # 単一 HTML(カメラ追跡つき)
python -m live2d_ai preview projects/owl_prince --poses "dn:AngleY=-10" --view 640,380,130,160 --out /tmp/pv
python tools/fidelity.py projects/owl_prince/out samples/ref12.png /tmp/err.png   # 休止ポーズの元絵との一致(PSNR)
```
- プレビューは headless Chromium(WebGL を swiftshader で)。`CHROME_PATH` で実行ファイルを指定できる。
- 公開物: `dist/owl_prince.html`(ダウンロードして Chrome で開く。Web カメラ追跡つき)。
- GPU・HuggingFace なし。機械学習モデルは使えない前提で、**人が画像を見て領域を決め、古典的画像処理で切る**。

## 構成
| 場所 | 内容 |
|---|---|
| `live2d_ai/decompose.py` | 領域+色ゲートでパーツへ分配、隠れた部分の補完、`unmix`(髪と肌の半透明分離)、`exclude`/`keep_big`/`clean_partial` など |
| `live2d_ai/synth.py` | 合成パーツ(`ref_patch` 参考絵から切り出し、`open_mouth_line`、`closed_eye` など) |
| `live2d_ai/build.py` | 仕様 → パーツ PNG + メッシュ + `rig.json` |
| `live2d_ai/headmodel.py` + `projects/*/head_model.json` | このキャラ専用の頭の奥行き(正面の幅 + 横顔の出っ張り) |
| `viewer/runtime.js` | WebGL ランタイム(head3d, translate/rotate/scale/opacity, ばね物理) |
| `viewer/tracking.js` | Web カメラ追跡(MediaPipe)。母音判定 `vowelWeights` |
| `projects/owl_prince/parts_spec.json` | どの画素をどのパーツにするか |
| `projects/owl_prince/rig_spec.json` | パラメータ、各パーツの動き、物理 |
| `tools/` | `zoom.py`(座標グリッド付き拡大)、`preview.py`、`fidelity.py`、`track_test.py` |

## 現在の仕様(ユーザーが決めたこと)
- 首の角度: 左右・かしげ ±5°、上下は 上+5°/下-10°(うなずき)。大きくは動かさない。
- 頭を動かすと、体全体もごく小さく一緒に動く(`body_follow`)。ジャケット・肩・時計・房は、頭に連動しない。
- 銀髪は首から下では動かない。耳+耳飾りは一緒に動く。肩のフクロウは頭に連動しない。
- まばたき: 参考絵の段階絵を段階的につなぐ。黒目は動かさない。笑顔: `Smile`。口: 母音 `VowelA/I/U/E/O`(参考写真)。
- 縁はくっきり(`edge`)。髪飾り・アクセサリーには縁取りを足さない。

## 未完了・次の作業(分担の目安)
1. **髪とアクセサリーの揺れ**(ばね物理の調整。Claude が着手中): 髪の房、前髪、リボン、チェーン、耳飾り、房(タッセル)。
2. 耳の形(うなずいたときのズレ)。2回、直したと言って直っていない。下向きの参考絵 `samples/nod_down_ref.png` の耳を `ref_gate` でキーフレームにする案は一度試して「戻して」と言われた(コミット `60e07a5`)。やるなら途中の姿勢の二重像に注意。
3. 上向き(+5°)・左右に傾けたときの耳。
4. 口の表情の追加(笑顔のときの口)、眉の動き。

## 並行作業の決まり(Claude と Codex が同時に作業するため)
- ブランチ: Claude は `claude/brave-hypatia-vswsvd`。**Codex は別ブランチ(例 `codex/<作業名>`)を切る**。同じブランチへ同時に push しない。
- **ファイルの担当を分ける**: 揺れ(Claude)は `rig_spec.json` の `physics` と `viewer/runtime.js` の `_physics`。Codex が耳・切り取りを触るなら、`parts_spec.json` のそのパーツと `decompose.py` に限る。同じ JSON の同じ箇所を同時に編集しない。
- `projects/owl_prince/out/` と `dist/` は生成物(`out/` は `.gitignore`)。**マージ後に必ず再ビルド**してから確認する。
- 仕様を変えたら `CLAUDE.md` の該当節に「何が原因で、どう直したか」を1〜3行で足す(次の人が同じ失敗をしないため)。
- ユーザーへ渡す前に、休止ポーズの一致(`tools/fidelity.py`)と、上下左右・うなずき・まばたきの画像を目視する。

## よくある落とし穴(抜粋。詳細は CLAUDE.md)
- 矩形/多角形で取る範囲が、他の部位(肩、背景の空白)に届いていないか確認する。届くと、その部位が頭と一緒に動く。
- 色の条件に「暗い色」を入れると、髪の影まで取る。肌は `Lab b ≥ 127.5`(髪は b < 125)で分ける。
- 隠れた部分の補完に髪の画素が混ざると、肌に灰色のまだらが出る。肌だけから埋める。
- 手で打った多角形が境界になると、その直線が「ズレ」として見える。色で境界を決める。
- 参考絵が別の描画(ぼやけた版)のとき、差分マスクは、その元になった絵(`base`)と比べる。
