# live2d_ai

1枚のイラストを、Claude Code への指示だけでパーツ分割して動かす(Live2D 風)ためのツール一式。

- **元絵の画素をそのまま使う**(再生成しない)ので、絵柄が変わらない。サンプルの休止ポーズは元絵と PSNR 45 dB 一致。
- パーツ分割 = 領域(多角形/楕円)+ 色ゲート + 手前優先の画素配分。隠れた部分は補完、無い部分(閉じ目・口の中)は描画で生成。
- 動き = 頭部の擬似3D回転、まばたき、視線、口、呼吸、ばね物理(髪・リボン・耳飾り・房)。
- 出力 = `rig.json` + パーツ PNG。WebGL2 ビューア(`viewer/`)、または単一 HTML(`dist/owl_prince.html`)。

## すぐ試す

`dist/owl_prince.html` をブラウザで開く(サンプル。スライダーで動かせる。マウス追従、Web カメラ追跡つき)。

```sh
pip install opencv-python-headless scipy pillow playwright    # 作る側のみ
python -m live2d_ai build projects/owl_prince
python -m live2d_ai serve projects/owl_prince                 # → http://localhost:8000/viewer/index.html?model=...
python -m live2d_ai preview projects/owl_prince --poses "r20:AngleX=20;blink:EyeLOpen=0,EyeROpen=0" --out /tmp/pv
python -m live2d_ai export projects/owl_prince -o dist/owl_prince.html
```

## 最新の操作

- 頭の回転範囲は左右・傾き ±5°、上下は上 +5°／下 −10°。横・縦の平行移動は別スライダーで広く動かせる。
- 口は「え」の形を使い、閉じ口からなめらかに開閉する。
- 笑顔はキー **1** で切替、**0** で真顔。自動で笑顔にはならない。ボタンでも操作できる。
- カメラでは「正面を較正」で中心を合わせ、「移動の感度」で反応を調整する。

比較画像・検証方法は [操作仕様](docs/controls.md) と [毛先・耳・Eの口の更新](docs/polish.md)。

## 自分のイラストで作る

```sh
python -m live2d_ai init my_model your_illustration.png
```

あとは Claude Code に「顔のパーツを取り出して」「まばたきできるようにして」「髪の毛先を揺らして」のように指示する。
手順と仕様の書き方は [CLAUDE.md](CLAUDE.md)。

## 現実的な限界

大きな首振りや横向き(隠れた面)は破綻する。±20° 程度までが実用。プロが描き足した Live2D の品質には届かない。
`.moc3` は出力できない。詳細は CLAUDE.md の「既知の限界」。
