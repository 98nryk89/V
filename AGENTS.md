# AGENTS.md — live2d_ai(Codex / 他のエージェント向けの引き継ぎ)

## 最新: MOTION-4の上下混入抑制と上向きの視線（2026-10-22）

利用者の左向き/左右かしげで上下が混ざる指摘に対し、新版は左右/かしげが主な動きの弱い上下成分を抑える。斜めの小さい上下も抑える意図的な仕様変更として説明する。上向き時の部分的なEyeBlinkだけで目を細めず、完全な瞬きは残す。黒目4パーツの上向き視線だけを旧1px→3pxへ。画像/メッシュ/マスク/共通runtime/旧HTMLは変更しない。MOTION-3の有効な方向設定を引継ぎ、html・bridgeのZIPで更新する。検証用入力と実機の確認を区別し、「実機で直った」と断定しない。docs/iphone-pitch-gaze-v4.md参照。

## 最新: 別フォルダの旧中継を再利用する経路を修正（2026-10-22）

portable/run.jsの旧処理はappIdだけを見て旧サーバーを再利用していた。これは確認できた不具合だが、利用者の実機での回転混線の原因と断定しない。新portable-motion/はモデル内容/起動フォルダ/版で一致確認し、自製品の旧中継だけをAPIで停止して切り替える。配布モデルのSHAも検証し、固有名HTMLと版表示を使用。新HTMLは中継の版不一致で追跡を開始しない。ZIPのhtml・bridgeだけを既存フォルダへ置換し、許可済み起動.commandは保持。方向はv3方式で初回記録し、古い方向設定は引き継がない。旧HTML/素材/起動セットの原本は維持。docs/iphone-verified-launch.md参照。

## 最新: iPhoneの方向変換を3方向の実記録へ作り直す（2026-10-22）

v2.2も実機で上下/左右/かしげが混線。固定の軸対応を再び推測して渡さない。v3は正面からの相対クォータニオンを求め、正面・下・右・右かしげを初回に画面内で記録し、3方向の逆行列で角度を分離する。古いlocalStorageは読まない。診断値の提出依頼は利用者が不要と明示したため取り下げる。検品は「左右入力でAngleY/AngleZ=0、上下入力でAngleX/AngleZ=0」を目標値と実パラメータの両方で行う。Node72件・ブラウザ4件、5姿勢の旧描画一致を確認。初回設定が必要な版と明示し、実機を未確認のまま「直った」と断定しない。旧HTML/素材/中継を保護する。docs/iphone-motion-v3.md参照。

## 最新: 下向きと横向きの混同を実機報告に合わせ修正（2026-10-22）

v2/v2.1の固定対応は実機で横向きがうつむきになった。旧「公式軸が正しい」という断定より利用者の実機報告を優先する。新v2.2は初期pitch=x(-)、yaw=y(-)、roll=z。位置や左右飽和を上下へ加算しない。画面内で正面C→実際の下向きを記録して軸/符号を合わせ、ブラウザへ保存できる。旧版を保持し、HTML/新設定2ファイルだけのZIP更新。Node62件+ブラウザ4件、5姿勢の描画一致。実機の物理的な向きの一致は利用者の次の確認事項。docs/iphone-pitch-v22.md参照。

## 最新: iPhoneの直接ファイル起動を案内（2026-10-22）

利用者が接続中のまま開いていたURLはfile:///。iPhone版は中継のHTTP接続画面から開く。中継のOrigin制限を緩めない。旧版を残したv2.1のHTML/入力を追加し、直接起動の案内・接続期限・受信エラー表示を実装。回転/表情/画像はv2を維持。Node55件+ブラウザ3件、5姿勢の描画一致を検証。詳細はdocs/iphone-connection-v21.md。

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
| `viewer/tracking.js` | Web カメラ追跡(MediaPipe)。顔位置と回転を分離、顎の開きで E の口を連続開閉 |
| `projects/owl_prince/parts_spec.json` | どの画素をどのパーツにするか |
| `projects/owl_prince/rig_spec.json` | パラメータ、各パーツの動き、物理 |
| `tools/` | `zoom.py`(座標グリッド付き拡大)、`preview.py`、`fidelity.py`、`track_test.py` |

## 現在の仕様(ユーザーが決めたこと)
- 首の角度: 左右・かしげ ±5°、上下は 上+5°/下-10°(うなずき)。大きくは動かさない。
- 角度に応じた小さい体の連動に加え、独立した BodyX/Y で全身を横 ±90px・縦 ±70px 移動する。ジャケット・肩・時計・房は頭と個別には回転しない。
- 銀髪は今回の指示で長髪まで控えめに頭へ連動する（末尾・docs/long-hair.md参照）。耳+耳飾りは一緒に動く。肩のフクロウは頭に連動しない。
- まばたき: 参考絵の段階絵を段階的につなぐ。黒目は動かさない。笑顔: `Smile`（キー1で切替、0で真顔。自動判定なし、初期値0）。口: 閉じ口から参考 E の `VowelE`（0〜1）へ連続開閉。笑顔時もこの口だけを使う。
- 縁はくっきり(`edge`)。髪飾り・アクセサリーには縁取りを足さない。

## 過去の引き継ぎ時点の未完了（現在の状態は末尾を優先）
ユーザーの不満は「切り取りが雑」「耳が揺れる」「髪の揺れの範囲が不明」。**切り取りは、ユーザーが渡した画像(下記)のアルファを正解として使う。多角形や色で大まかに取らない。**

1. **髪の作り直し(途中)**: `projects/owl_prince/hair_head_alpha.png`(ユーザーの髪レイヤーのアルファ − アクセサリー)から新パーツ `hair_head` を作った。**旧パーツ `hair_front` `hair_side_L/R` `hair_back` がまだ残って重なっている**ので、`hair_head` に統合して消す。首から下の長い銀髪は、ユーザーの指示で「動かさない」(体に戻す)。眉パーツ `browL/R` の四角い箱が髪を取っているので、眉は眉の形だけにする。診断の方法は `CLAUDE.md` の「髪の切り取りは…」節。
2. **耳(最重要・何度も指摘された)**: 耳は顔の一部で、**揺らさない。頭と同じ動きだけ**。耳飾りの輪(フープ)も耳と一緒。輪より下の鎖と宝石だけ揺らす。耳の肌の欠け・揺れて見える原因は、髪の下に隠れた耳の肌が元絵に無く、補完で欠けること。**正解の画像がある**: `samples/skin_alpha.png`(ユーザー提供、髪なし・透明背景の顔/首/耳)。元絵との位置合わせは `samples/skin_alpha_aligned.png`(顎・目は1px以内、耳は局所的に4〜6pxずれていたので耳だけ別に平行移動して `skin_layer.png` を作った。コミット `8fd0680`)。それを下地パーツ(`synthetic: aligned_layer`)として敷く方法は、一度試して「悪化した」と戻された(`git revert`)。**悪化の原因は未確認**(灰色の四角が出た=胴体の補完 `extent_in_figure` の問題だった可能性が高い。それは別途直した)。やり直すなら、1コミット1目的で、ユーザーに見せる前に、耳を揺らす/うなずく画像を目視する。
3. 左耳: 右耳は、ユーザーが塗った注釈(`samples/ear_annot.png` → `ear_R_mask.png`/`earring_R_mask.png`)で作った。左耳は未対応(ユーザーに同じ注釈を頼む)。
4. リボン右下の灰色の欠片(揺らすと出る。原因未特定)。
5. 髪とアクセサリーの揺れの調整(強さ・メリハリ)。ユーザーは「感度が高すぎる」「どこを揺らしているか分からない」と言った。揺らす部分と揺らさない部分のメリハリを付ける。

## ユーザーが渡した、正解として使える画像(`samples/`)
`ref12.png`(元絵、透明背景の高精度切り抜き。これが `source`)、`hair_layer.png`/`hair_layer_aligned.png`(頭の髪+仮面+リボン+耳飾り、アルファ付き)、`skin_alpha.png`(髪なしの肌)、`ear_annot.png`(耳=赤・耳飾り=緑の塗り)、`nod_down_ref.png`(下向き-10°の絵)、`blink_*.png`(まばたき)、`vowel_{a,i,u,e,o}.png`(母音の口)、`blink_7.png`(笑顔)。

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

## Codex 修正後の状態（2026-10-16、上記の「途中」記述より新しい）

- `codex/cutout-repair` で作業。旧4髪パーツは parts_spec から削除。頭の髪は提供アルファの `hair_head`、長い銀髪は body に戻した。rig_spec の未使用定義は並行作業への影響を避けて残している。
- 眉と左耳の肌は face に統合。右耳は最新修正で剛体パーツに分離（末尾参照）。顔・耳の見えている元絵画素を色条件で塗り直す処理を外した。隠れた耳は履歴にあった提供 RGBA から補う。耳飾りの輪より下だけが揺れる設定は維持。
- 詳細・比較・検証方法は `docs/cutout-repair.md`、原因は CLAUDE.md の Codex 節。テストはビルド後に `python -m unittest discover -s tests -v`、既存 fidelity/physics/preview で確認する。
- 残作業の優先順: (1) ユーザーの修正版での動作確認、特に左右の耳と髪の境目。(2) 頭の髪を毛束ごとに分ける追加調整と長髪とのつなぎ目の確認。(3) リボン右下の灰色片の切り分け。(4) 実機カメラ。うなずきの参考絵と完全一致する立体・形状にしたわけではない。

## 移動・口・表情の操作更新（切り取り修正後の最新仕様）

回転の範囲は維持し、BodyX/Y は全パーツ共通の平行移動。カメラの位置合わせは「正面を較正」、移動量への反応は「移動の感度」で調整する。数字キー1で笑顔を切替、0で真顔。詳細と確認画像は `docs/controls.md`。検証は Python の13件（ブラウザ2件を含む）と `node --test tests/tracking.test.cjs` の7件。実機カメラは未確認、検出結果を模した入力でカメラ側の変換処理を確認した。

## 最新: Eの連続開閉・毛先・右耳・耳飾り裏（2026-10-16）

- 口は VowelE の1種類。0〜1の縦開きと時間的な平滑化を使い、Aの二値切替は廃止。笑顔は引き続き手動。
- 頭の髪は hair_head_clean_alpha.png。細い斜めの毛束も連結として残し、静止した body に髪の縁が残らないようにした。元の提供髪マスクは保存している。
- 右耳の肌 earR_skin は提供耳注釈由来のマスクで作り、金具と同じ深度121.839の剛体面。顔の曲面に混ぜてつぶさない。肌に物理は付けない。
- 耳飾り裏の銀髪は近隣色から局所補完。左耳飾りは髪を巻き込まない輪郭にした。マスク・補完画像は python tools/refine_cutouts.py で再生成。詳細・比較は docs/polish.md。
- 残作業: ユーザーによる実際のカメラ・背景での確認、必要なら耳付近の補完の追加調整。単一絵で隠れていた髪の線画は近似で、すべての角度の完全復元ではない。回転・体移動の範囲は維持している。

## 最新: 長髪まで切り出して連続して動かす（2026-10-16）

- 「首より下の長髪は固定」という旧指示は今回のユーザー指示で更新。hair_complete_alpha.png で頭〜毛先を一つの hair_head メッシュへ切り出し、耳の下から下方へ連続的に頭の追従率を弱める。
- 色だけの抽出はシャツ・襟の金属・フクロウも拾う。long_hair_regions.json の髪領域と除外指定、tools/refine_long_hair.py で再生成する。暗い根元と細い先端を落とさない。
- 耳飾り裏の銀髪は body から動く髪へ移した。hair_under_face は顔裏の隠れた補完だけを担当し、hair_head と同じ変換・深度を使う。服とフクロウには髪の回転を追加しない。
- 原因・比較・検証は docs/long-hair.md。元の画像・マスクと物理ドライバ本体は維持。未完了の優先順は、実機カメラでの確認、必要に応じた細い髪と服の接点の追加調整。

## 最新: 仕上がりを保った瞬き・眉・襟・毛先（2026-10-16）

- 人の瞬きは目の範囲だけを鮮明な段階絵で短く切り替える。眉や髪まで参考絵でぼかさない。フクロウは OwlEyeOpen と独立した自動タイマー、チェックボックスで確認できる。
- 髪に混入していた眉の線と黒い襟の画素を戻し、首が動くと出る襟との透明な隙間は白い襟の局所的な裏側補完で埋める。
- 髪本体の設定は維持。hair_tip_L/R の2か所（合わせて髪の約0.7%）だけを既存PhysHairL/Rで小さく揺らす。耳は揺らさない。物理ドライバ本体は触らない。
- 現在41パーツ、Python20件＋Node7件。再生成は従来の髪マスク生成後に tools/refine_details.py、build/export。比較・コミットごとの目的・戻した場合の再生成手順は docs/details.md。
- 次の確認は実機カメラでの瞬きの見え方と、必要なら2か所の毛先の強さの微調整。大きな作り直しはしない。

## 最新: 眉の横断線・カメラの首回転（2026-10-16）

- 眉の保護領域で前髪を切らない。提供hair_head_alphaで髪を保護し、髪がない露出した眉だけを顔へ戻す。
- カメラはMediaPipeの3D顔行列から角度を取り、正面の較正姿勢との差で左右5度・上5度・下10度、首かしげ±5度に追従。最初の有効な姿勢を初期基準にし、正面を較正すると移動・回転とも0へ戻る。行列が不正/なしなら2D追跡へ戻る。
- BodyX/Y、全体リグ・耳・物理・フクロウ・毛先は維持。Python20件＋Node10件、比較は docs/brows-rotation.md。実機カメラは未確認。

## 最新: 下向きの眉・手動の驚き顔（2026-10-17）

- 露出した眉だけでなく目/まぶたも髪から顔へ戻す。前髪は提供アルファで保護。tools/refine_details.py で再生成。
- 正解画像に samples/surprised_ref.png（ユーザー提供ZIP内の元PNG）を追加。キー2/驚きボタン、1/笑顔と排他、0/真顔/リセットで解除。驚きでも瞬き・Eの口で発話可能。デフォルト真顔。
- 44パーツ、Python20件＋Node10件。比較と戻し方は docs/surprise.md。回転は左右/上5度・下10度を維持。未完了は実機カメラでの確認と必要な微調整。

## 最新: 眉の肌への固定・顎の輪郭・カメラ自動A/I（2026-10-17）

- 眉を横切る髪の小領域を肌と同じ深度・変形へ合わせ、そこだけ前髪回転を除外。眉の表情追従なし。笑顔・驚きのパッチは目だけ。
- 左/下向きの顎の線の圧縮を緩和し、faceメッシュは4px。首の旧顎の線は tools/refine_face.py → neck_underjaw.png の局所補完で隠す。
- 口は旧E単独を廃止し、閉じ口・参考A・参考Iのみ。MouthForm=0/1をカメラで自動判定、MouthOpen=0〜1で滑らかに開閉。A/Iを混ぜない。驚き専用口も廃止。保存済み vowel_i.png が今回の添付と同じ歯を見せる参考。
- 44パーツ、Python22件＋Node12件。操作・比較・戻し方は docs/face-mouth.md。回転/移動の範囲・物理ドライバは維持。未完了の優先順は実機カメラでの口判定と眉/輪郭の確認、必要な感度の微調整。

## 最新: 低感度のA/I/E口・低感度の自動笑顔（2026-10-17）

- 最新指示でEを再追加。MouthForm=0:A/1:I/2:Eをカメラ判定し、共通MouthOpenで一つだけを連続開閉する。小さな動きを無視するデッドゾーンと閉じ判定のヒステリシスを追加。
- 自動笑顔を試す指示で、初期ONの低感度チェックを追加。両側の強い笑顔が約.6秒継続したときだけON、弱く戻って約.35秒で解除。数字1/0/2や手動ボタンで自動判定を止める。驚きは手動のまま。リセットは自動笑顔ONへ戻す。
- 45パーツ、Python22件＋Node16件。操作・閾値・比較は docs/low-sensitivity.md。眉の固定・輪郭・移動/回転の範囲・物理ドライバは維持。未完了は実機カメラでの感度確認と必要な微調整。

## 最新: 感度を少し上げる微調整（2026-10-17）

口はjaw>.18 / 唇差>.09から反応、jaw .13〜.55を0〜1へ変換。自動笑顔は両側スコア>.80を約.45秒保持するとON。小さな動きの除外と手動優先は維持。今回の検証はNode17件＋配布HTML/元ビューアの2件。詳しい現在値は docs/low-sensitivity.md。実機での感度確認は未完了。

## 最新: 自動の驚き顔・黒目の追従（2026-10-17）

- 驚きも笑顔と同じ.80超を約.45秒保持で自動ON、.55未満を約.35秒で解除。両側の見開きが必要。瞬き・片側・短い動きでは起動せず、同時検出は驚きを優先。初期ONの独立チェックを追加。
- 数字1/0/2や表情ボタンで笑顔/驚きの自動判定を両方停止し、手動を優先。リセットは両方ON。口の感度とA/I/Eの排他は維持。
- 通常/驚きの虹彩と瞳孔を元画素から切り出し、AngleX/YとBodyX/Yで最大およそ左右3px・上下1.5pxだけ追加追従。全身共通Body移動に対して黒目のみ追加±1/±.5pxを持つ。眉とまぶたは追従させない。クリップ用の固定開口と、隠れた白目の局所補完を追加。再生成は tools/refine_gaze.py。
- 51パーツ（新規6枚のうち4枚は非表示のクリップマスク）、Python25件＋Node19件。比較・原因・戻し方は docs/surprise-gaze.md。実機カメラでの感度確認と必要な微調整が未完了。

## 髪を固定する試験（2026-10-17、最新指示を優先）

- ユーザー指定で前髪・毛先の揺れを停止。頭髪の顔への追従は残し、y520→760で二乗減衰し、胸元以降は体に固定する。切り抜き画像は維持する。以前の長髪追従・毛先物理の仕様は比較用の旧版。
- 顔・耳・口・目・表情判定の設定は維持。物理ドライバ本体は変更しない。
- 直前の確定版は af92aabfd565876cb2afecfeb6b74cf128469d33。試験は1コミットでソース・HTMLをまとめてrevert可能。比較画像・復元方法は docs/hair-fixed-experiment.md。

## 別キャラ制作の共有資料（2026-10-18）

メンバーへの指示書は docs/character-production-guide.md、記入式依頼は docs/character-request-template.md。座標・色条件・マスク・頭部形状はキャラ専用で、画像の単純置換では流用できない。新キャラは別プロジェクトに分離し、既存モデルを保持する。今回の追加は文書のみで動作仕様は変更しない。

## 腕・衣装の外側追加（2026-10-19、最新）

- 元画像の外に存在する腕・腰まわりを、提供wide_frame_ref.pngから追加。顔・髪・表情・既存51パーツのメッシュと動きは維持し、52番目のframe_extensionをbodyと同じ呼吸/共通移動で描画する。
- tools/extend_frame.py → build → export。元絵・既存マスクの再生成は不要。parts_spec.frame_extension指定時のみ旧画像の左右・下端45pxを透過して追加層につなぐ。viewは[-430,-110,2000,1730]。
- 比較・再生成・戻し方はdocs/full-frame.md。直前の版はecf98c9f5e9d2ac2f238426d400fa8ed4a2dab11。Python27件＋Node19件。実機カメラ/OBSの確認は利用者PCで行う。

## 衣装の小修正（腕追加後）

- 仮面のリボン/鎖に混ざった肩の銀髪を専用マスクで除外。胴の追加層は境界色をなじませ、固定されたタッセルの残像を除く。
- hangR3は既存の房の画素で先まで補った一体のRGBAへ差し替え、キャンバス外まで同じメッシュで小さく揺らす。52パーツ。
- BodyYの変化にだけ反応するPhysSleeveを追加し、袖の外側のみ最大5px/1度。顔・長髪は揺らさない。既存physicsと_physics本体は維持し、_sleeveFlutterを別に追加。
- 再生成: tools/extend_frame.py → tools/polish_costume.py → build → export。加工済み追加画像へpolishだけを繰り返さない。詳細・比較はdocs/costume-polish.md。Python29件＋Node19件。戻す基準はe43e15724691463c2d3269f978f2c74188ff417b。

## リボン裏の補完停止・背景片とタッセルの透過調整（最新）

- リボン裏の銀髪色の再構成をfade_exposedで停止。見えている実際の髪は残す。布・金属の低透明度の縁もリボンへ戻し、鎖は宝石とリンクの範囲だけに限定。
- リボン周辺の小さな独立片だけをtrim_islandsで除く。領域を横切る毛束・大きな飾り・細い鎖は消さない。
- タッセルのbleedを0、房のclose=2を維持。背後は局所の暗い衣装色、元の襟補完は保存。大きい房は補間と輪郭を軽く調整。
- 生成順は従来どおりextend_frame→polish_costume→build→export。比較と復元はdocs/ornament-alpha-cleanup.md。52パーツ、Python32件＋Node19件。動きの設定とランタイム/追跡コードは変更しない。戻す基準は15526746be45360a16b3c1c5fd98de30e30a7926。

## 最新: リボン先端に接する銀髪の補完（2026-10-19）

リボン裏の一括補完停止が、最下段に潜る実際の毛束まで落としていた。polish_costume.pyのtip_hairの小範囲だけ、hair_headの補完禁止から除外する。body側・上段リボンの透過は維持し、リボンに髪を割り当てない。docs/ribbon-tip-hair.md参照。顔・物理・表情は変更しない。

## 最新: 先端の銀髪を自然につなぐ（2026-10-19）

20pxずらしただけの補完は毛筋・明暗がずれ、輪郭も角張った。polish_costume.pyのribbon_tip_underlapで曲線の輪郭と、元の髪を境界条件とする局所Poisson補間に変更。リボン先端の暗い縁を布へ戻し、髪に紫線を残さない。旧補完参照のリボン裏の平面は消すが耳裏は保つ。docs/ribbon-tip-blend.mdを最新とする。物理・顔・表情・衣装は維持。

## 最新: 左上腕の半透明を修正（2026-10-19）

元の腕と追加画像の輪郭の差で、追加層が存在しない上腕まで旧画像端のフェードがかかっていた。tools/extend_frame.pyで左上腕の追加層だけを局所的に位置合わせし直す。旧画像の切り取り・フェードは維持し、元画像端の切れた布を露出させない。docs/sleeve-opacity.md参照。頭部・表情・物理・元の全パーツは維持。

## iPhoneトラッキング中継の追加（2026-10-20）

kamikan-bridge/は独立したNode.js 22以上のUDP→WebSocket中継。config.jsonのiphoneIpとhtmlDirを設定し、初回npm ci、以後npm start。UDP 21412へ毎秒要求、UDP 11125受信、HTTP/WSはlocalhost:8765。公式のBlendShapes配列と未知フィールドを原文のまま転送する。npm testで中継9件を検証。既存HTML・モデル・追跡コードは変更しておらず、HTML側のiPhone接続はまだ未実装。README.mdを参照。

## iPhone入力を別HTMLで試験（2026-10-21、最新）

- 完成HTML3ファイルと全画像・rig・runtime.js・tracking.jsは変更禁止のまま。新しいdist/owl_prince_iphone_test.htmlだけに入力を追加。旧版owl_prince.htmlを開くだけで即復帰できる。専用ブランチcodex/iphone-tracking-test、単一目的コミット。
- viewer/tracking-input.jsがiPhone/既存Webカメラを抽象化。?source=iphoneが初期値、?source=webcamは開始時にだけdist/tracking_webcam_legacy.jsを取得しMediaPipeを起動。iPhone時はカメラ処理・外部顔認識依存を取得しない。
- ws://localhost:8765の公式生JSONを使用。Cで正面/真顔/顎開きの基準を記録、時間基準の平滑化は設定可。FaceFound=falseまたは750ms無受信で滑らかに正面・真顔へ。WebSocketは毎秒再接続。
- 自動笑顔、驚きはホットキー2。iOSホットキー1〜8の割当はdist/owl_prince_tracking_config.json。既存の数字1/2/0・表情ボタンは維持。A/I/Eは近似判定し排他、眉・髪・物理は変更しない。独立眼球回転など未対応の動きは増やさない。
- 再出力はpython tools/export_iphone_test.pyのみ。完成HTML内の52パーツrigをそのまま複製する。モデルbuildや画像加工は不要。試験版JSONは再出力でも上書きしない。
- 検証: 新旧追跡Node31件、中継9件、実UDP→中継→Chromiumと遅延カメラ/5姿勢の旧版描画完全一致3件、合計43件成功。元HTML/追跡/描画と既存画像113ファイルのハッシュ不変。表示画像/workspace/iphone-integration-check/iphone-test.pngを目視。手順はdocs/iphone-tracking-test.md。
- 未完了優先順: 利用者Macで実iPhone→新HTMLの方向/位置感度/母音判定を確認し必要なら新しい設定だけ調整、実Webカメラ/OBSの確認。実iPhone→中継までの受信は利用者が確認済み。Claude担当physicsと_physicsには触らず、同じブランチへpushしない。

## Webカメラ完成版の配布パッケージ（2026-10-21）

配布用dist/lunaris_webcam_distribution.zipは、完成版dist/owl_prince.htmlをバイト変更せず収録したもの。Lunaris_Webcam/内にHTML、はじめに.txt、操作説明.html、VERSION.txtを同梱。受取側は解凍してChromeでHTMLを開きWebカメラ開始。iPhone/Node/npm/中継は不要、顔認識データ取得にネット接続が必要。再作成はpython tools/package_webcam_distribution.py。ユーザー向け説明原本はdocs/webcam-user-guide.html。MacのOBSはmacOSスクリーンキャプチャ、クロマキーは実装の緑#6fcf97を指定。旧Webカメラ完成版は自動笑顔/驚きが初期ON、Cキー較正ではなく「正面を較正」ボタン。iPhone試験版と混同しない。新規軽量化やモデル変更は行っていない。

## 別キャラ用Codex共有キット（2026-10-21）

dist/codex_character_creation_kit.zipを追加。docs/codex-character-kit/が指示書原本、tools/package_codex_character_kit.pyで再作成。初回/修正プロンプト、素材・依頼・検品・環境・引継ぎ書式を同梱。starterに共通Python/描画/追跡/プレビュー/追跡単体検証をそのまま収録し、元リポジトリ権限なしでも別キャラに着手できる。referenceの完成HTMLは旧版と同じ画素・コード。元キャラの専用画像・マスク・Git履歴は未同梱で、referenceの仕様JSONは読解用。initだけで完成しない点、キャラ別の切り抜き/頭部形状/素材が必要な点、Webカメラ標準とネット依存を明示。既存モデルと追跡・描画コードは変更しない。

## Mac・iPhoneのダブルクリック配布セット（2026-10-22、最新）

- dist/lunaris_iphone_mac.zip。HTML・中継・実行権限付き起動.command・接続GUI・日本語説明・ws 8.22.0（LICENSE含む）を同梱。Node.js本体は含めず、Macに既存の22以上を使用。利用者はnpm/JSON編集不要。未導入なら公式LTSのpkgを初回だけ案内。
- kamikan-bridge/portable/が原本。CLI実行の旧server.js/config.json方式も維持。既存createBridgeに任意のHTTPハンドラ、IP再設定、状態取得を追加し、初回IP未設定ではUDP要求しない。設定GUIから保存すると受信ソケットを保ったまま接続先を更新。HTTP/WS8765、UDP受信11125、iPhone要求21412。
- Macの設定は~/Library/Application Support/KamikanBridge/owl-prince/connection.jsonへ保存し、フォルダ差し替え後も保持。OriginとJSON POSTを確認し、設定はモデルのHTTPフォルダ外へ保存。モデル画面の感度/較正は従来通りページ内だけ。
- 前回のdist/owl_prince_iphone_test.htmlをそのまま複製。完成版3HTML・画像・viewer/runtime.js/tracking.js/tracking-input.jsは変更しない。自動笑顔、驚きホットキー2、C較正を維持。OBSの背景色はiPhone試験版の#00ff00。
- 再出力はpython tools/package_iphone_mac.py。node_modules/wsがない場合のみ制作者がkamikan-bridgeでnpm ci。新旧中継14件、追跡31件、旧ブラウザ3件、解凍ZIP→GUI保存→模擬iPhone→実モデル→終了1件、合計49件成功。抽出した実行ファイルでもスペースを含むパスから起動、二重起動時再利用、API終了・正常終了を確認。ZIPの実行権限と全ファイルハッシュを照合。画像は/workspace/iphone-portable-check/。
- 今回はLinuxで起動ファイルとChromiumを検証。実Macでのダブルクリック許可、実iPhoneからの入力、OBS録画は利用者が次に確認。既存中継が残っていれば先にControl+Cで終了し、ポート競合を避ける。Node内蔵・iPhone自動検出・新規軽量化・透明OBS専用画面は未実装。

## iPhoneの回転・正面安定化v2（2026-10-22、最新）

- 利用者の実機確認で下向きが回転しない/正面付近がずれると判明。公式受信例のUnity Euler(-Rotation.y,-Rotation.x,Rotation.z)を確認し、旧版で左右/上下軸を逆に解釈していたことを特定。新V2はAngleX=-Rotation.x差、AngleY=Rotation.y差、AngleZ=Rotation.z差。旧版の入力表の軸説明は既知の誤りとして扱う。
- sourceはviewer/tracking-input-v2.js / iphone-v2.html、新出力はdist/owl_prince_iphone_v2.htmlとtracking_config_v2。位置倍率の初期値10→.2、微小除外は位置.1/角度.35度。Cは約.3秒の安定した複数フレームの中央値、記録成功を表示。静止基準を自動で動かす方式にはしない。
- 配布はdist/lunaris_iphone_pose_v2_update.zip。実行ファイルなし。現在のMacセットを複製して旧版保管後、html内のモデルHTMLと新設定の2ファイルだけを交換する。既に許可済みの起動.command・中継・Node・旧設定を取り替えない。再読み込み後Cで合わせる。
- 旧Webカメラ/旧iPhoneの全HTML・入力コード・旧ZIP・画像・中継は変更しない。新入力17件＋旧入力31件、旧配布ZIPへ2ファイル更新した実経路のブラウザ2件、計50件通過。下向きのみ/左右のみ/正面復帰/微小ノイズ/表情を検査し、5姿勢で旧描画とハッシュ一致。画像は/workspace/iphone-pose-v2-check/で目視。
- docs/iphone-pose-v2.mdを参照。再生成はtools/export_iphone_pose_v2.py→tools/package_iphone_pose_v2_update.py。実iPhoneでなお大きくずれるかの確認は次。生入力のドリフトやiPhone自身の移動まで全て消えたとは主張せず、必要なら画面の診断値コピーで正面のraw/neutral/paramsを確認する。
