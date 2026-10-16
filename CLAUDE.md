# live2d_ai — 1枚絵から「指示だけ」で動くモデルを作る

ユーザーは Live2D Cubism / VTube Studio を使わず、**Claude Code への口頭指示だけ**でイラストをパーツ分割し、動かしたい。
最重要の方針: **動く部分を AI で再生成しない。元絵の画素をそのまま切り出して変形する。**(再生成すると元と少し違ってしまうため)
生成するのは「元絵に存在しない画素」(閉じ目の線、口の中、パーツの裏側)だけで、`live2d_ai/synth.py` と `decompose.py` の補完で行う。

## 作業の流れ(ユーザーの指示への対応)

1. **画像を見る。** `python -m live2d_ai zoom <png> x0 y0 x1 y1 --scale 4 --step 10 -o /tmp/z.png` で座標グリッド付きに拡大し、Read で画像を見て座標を読む。
   小さいパーツ(目、口)は 8〜9 倍で見る。座標は元画像のピクセル座標。
2. **パーツ仕様を書く**(`projects/<name>/parts_spec.json`)。「顔のパーツを取り出して」「前髪を分けて」などの指示は、ここに part を足すことで実現する。
3. **確認する。** `python -m live2d_ai labels projects/<name> -o /tmp/l.png` で「どのパーツがどの画素を取ったか」を色分け表示。穴・取りこぼし・取りすぎを直す。
4. **ビルドとプレビュー。** `python -m live2d_ai build projects/<name>` →
   `python -m live2d_ai preview projects/<name> --poses "r20:AngleX=20;blink:EyeLOpen=0,EyeROpen=0" --view x,y,w,h --out /tmp/pv`
   → 出力 PNG を Read で必ず目視する。**休止ポーズ以外のポーズ**(首振り・まばたき・物理)で破綻を探すのが本番。
5. **リグ仕様を書く**(`rig_spec.json`)。「こういう時はこう動く」という指示はここに書く(下の辞書参照)。
6. 納品: `python -m live2d_ai export projects/<name> -o dist/<name>.html`(単一 HTML。ブラウザで開くだけで試せる)。

画像が「市松模様の背景が焼き込まれた RGB」の場合、`build`/`labels` が自動で背景除去する(`matte.py`)。
このコンテナは GPU なし・HuggingFace 不可。ML モデルは使えないので、**私(Claude)が画像を見て領域を決め、古典的画像処理で精密に切る**。

## parts_spec.json の書き方

```jsonc
{"source": "../../samples/source.png",
 "parts": [
  {"id":"face", "z":5,                  // z が大きいほど手前。手前のパーツが先に画素を取る
   "zone": [[x,y],...],                 // 取ってよい領域。多角形 / 多角形の配列 / {"ellipse":[cx,cy,rx,ry,deg]}
   "color": {...},                      // 任意。色ゲート(下記)
   "extent": [[x,y],...] | "all",       // 隠れた部分も含む本来の形。手前に隠れた画素を補完する
   "bleed": 8,                          // 手前パーツの下へ潜り込ませる量(動いた時の隙間防止)
   "close": 3, "fill_holes": 200,       // 穴埋め(髪の影など)
   "fill_gate": {...}}                  // 補完の元にしてよい画素(色)
  {"id":"eyeL_closed","z":15,"synthetic":{"type":"closed_eye","pts":[[x,y],...],"width":4.6}},
  {"id":"mouth_open","z":12,"synthetic":{"type":"open_mouth","center":[x,y],"rx":21,"ry":17}}
 ]}
```

色ゲート: `{"near":[[r,g,b],..],"tol":14}` / `{"far":[...],"tol":14}`(Lab 距離) / `{"lab":{"L":[lo,hi],"a":[..],"b":[..]},"soft":3}` / `{"any":[ゲート,...]}` / ゲートの配列は AND。
実測した値: このサンプルの肌は Lab(237,133,134) と非常に均一、銀髪は b≈122、白シャツは b≈126(`lab.b` の上限で分けられる)。

コツ:
- 何も指定しない最背面パーツ(`zone:null`)が「残り全部」を受ける。`extent:"all"` にすると全域が完全な下地になる(手前を動かしても穴が開かない)。
- 髪の毛束のような細かいものは「多角形(ざっくり)+ 色ゲート」で取る。多角形は厳密でなくてよい。
- 目: white(白目,extent あり) / iris(虹彩,`clip` で白目の形に切る) / lash(睫毛,暗色ゲート) / closed(合成の閉じ目線)。
- 動かすパーツの元の位置に、取り残しのかけらが `body` に残っていないか `labels` で見る(動かすと浮いて見える)。

## rig_spec.json の書き方

`params`: 動かすスライダー(`id,min,max,default`)。`parts.<id>.effects` は上から順に頂点へ適用される。

| effect | 内容 |
|---|---|
| `head3d` | 頭を球とみなした擬似3D回転。`center,R,zoff`(奥行きオフセット。手前の前髪は +、後ろ髪は −)、`yaw/pitch/roll` に param 名、`pivot`(首の付け根)、`weight` で部分適用 |
| `translate` / `rotate` / `scale` | `param` と `map:[[p,値..],..]`(区間線形)。`rotate` は `pivot` と頂点ごとの `weight`(曲がり) |
| `opacity` | param → 不透明度(目の開閉のクロスフェード、口) |
| weight | `{"mode":"y","from":..,"to":..,"pow":..}` / `"x"` / `{"mode":"dist","pivot":[x,y],"len":L}` — 根元 0 → 毛先 1 |

`templates` に effect 列を名前付きで定義し、`"@name"` で展開。`physics`: 減衰ばね(`output` の param を -1..1 で駆動。`inputs` の param の加速度で揺れる)。

**効果の順序が重要**: まばたき・視線・物理の揺れ(元絵座標系の操作)を先に、`head3d` を最後に置く。
イラストレーターの知識の置き換え:
- 首振り: 顔の目鼻口は `zoff 0〜6`、前髪は `zoff +25`、後ろ髪は `-25`、耳飾りは顔と同じ(`zoff 4`)にすること。奥行き差が大きいと顔からずれて見える。
- 髪の長い束は `head3d` の `weight` を根元1→毛先0にして、毛先は体に残す。
- まばたき: 白目・虹彩・睫毛を**同じ比率**で潰し、閉じかけ(open<0.25)で合成の閉じ目線にクロスフェード。比率がずれると隙間が出る。
- 揺れ物の符号: `rotate` の正の角度は毛先が画面左へ動く。頭が右へ動いた時に毛先が遅れて左へ行く → `map:[[-1,+deg],[1,-deg]]`。

## キャラ専用の頭部モデル(`head_model.json`)

汎用の球ではなく、**そのキャラの測定値**で頭の立体を作る(`live2d_ai/headmodel.py`)。
- 正面の絵から: 高さごとの顔の左右半幅(左右非対称)。顎のラインは `parts_spec` の顔のポリゴンと同じ線を使う。
- 横顔の絵から: 高さごとの顔の出っ張り(額・鼻・唇・顎)と鼻の山。`side_to_front_y` で、横顔と正面の高さを目・口・顎の位置で対応づける。
- `rig_spec.json` の `head_model` で読み込み、各パーツの `depth:{"layer":"face|hairfront|dome|side|neck|const"}` から、メッシュ頂点ごとの奥行き `mesh.z` をビルド時に計算。`head3d` の `vz:true` が使う。
- 輪郭際の奥行きは `edge_floor` で下げ止める(0 に落とすと、輪郭際の絵が何倍にも引き伸ばされてギザギザになる)。
- 顔のパーツは `clean` で肌の色以外の画素(髪の縁など)を除き、肌色だけで補完する。眉・目・口は顔の面に乗せ、`rigid:1`(1枚の剛体として動かす)。

## 検証の流儀

- 休止ポーズの再現度を数値で確認する(`dist/*.html` を headless で開き、元絵との PSNR を取る。サンプルは 45 dB)。
- `tools/preview.py` の `render_anim` は物理を実時間で回してフレームを撮れる。
- `viewer/tracking.js`(Web カメラ追跡)は開発コンテナで実機検証できていない。符号は UI の反転チェックと「較正」で合わせる。

## 既知の限界(正直に)

- 首振りは **±12° が上限**(`AngleX/Y/Z` の min/max)。ユーザーが「自然に保つ方を優先、大きくは動かさなくてよい」と決めた。奥行きは `head3d` の `k:0.5` で圧縮し、層ごとのずれを小さくしている。±15° 以上は耳・顎・髪の重なりで破綻する(見えない面が元絵にない)。横向きは変形では作れない。
- 手作業の Live2D のように「角度ごとに描き足した」品質には届かない。特に髪のハイライト、まつ毛の立体感。
- `.moc3`(Live2D Cubism 形式)は出力できない(プロプライエタリ)。出力は独自 `rig.json` + WebGL ビューア。
- 背景除去は「彩度ほぼ0の市松」前提。別の背景の画像は別途切り抜いてから渡す。
