# 00. ツール選定（2026-10 時点）

目標: **大手事務所所属 VTuber と同等の全身 Live2D モデル**を、生成イラスト 1 枚から作り、配信で動かす。
Cubism に限定しない前提で、使えるツールを比較した。

## 結論

| 工程 | 採用 | 理由 |
|---|---|---|
| 高解像度化 | Real-ESRGAN（アニメ用、`tools/upscale.py`） | CPU でも動く。済 |
| 背景透過 | ISNet-anime（`tools/remove_bg.py`） | 済 |
| **パーツ分け＋描き足し** | **See-through（AI 自動レイヤー分解）→ 高解像度化（`tools/transfer_highres.py`）→ 手作業で仕上げ** | 最も工数がかかる工程を AI で下書きできる |
| **リギング（動きの組み込み）** | **Live2D Cubism**（外注、または AI 補助機能を使って自作） | 理由は下記 |
| トラッキング | VTube Studio ＋ iPhone | |
| 配信 | OBS | |

### リギングを Cubism のままにする理由
- **VTube Studio が読み込めるのは Cubism の書き出し形式（moc3）だけ**。他のツールで作ると、トラッキングソフトも配信の環境もまとめて変えることになる。
- 大手事務所の 2D モデルはほぼすべて Cubism 製。目標とする品質に届いた実績があるのは Cubism だけ。
- Cubism 自体に AI の補助機能がある: 5.0 の顔の動きの半自動生成とモーションシンク（音声からの口パク）、5.1 のデフォーマと揺れの自動生成。自作する場合の作業量はかなり減る。
- 「Cubism を無理して使わない」の実現方法は、**Cubism のリギングを外注する**こと。こちらの成果物（PSD とパラメータ仕様）を渡せば、そのまま作業に入ってもらえる。

### 検討して見送ったもの
| ツール | 内容 | 見送った理由 |
|---|---|---|
| Stretchy Studio | See-through の PSD をブラウザ上で自動リギングする | VTS 非対応。品質は試作レベル。**動きの試作（プレビュー）用**としては使える |
| iki | AI エージェントがパーツ作画からリギングまで行う 2D パペットエンジン（MIT） | 0.x で、本人も「まだ本番向けではない」としている。独自形式で VTS 非対応 |
| Inochi2D | オープンソースの Live2D 代替（専用トラッキングソフト Inochi Session あり） | エコシステム・品質の実績が Cubism に及ばない |
| Qwen-Image-Layered | 画像生成でレイヤーを作り直す方式 | 元絵を分解するのではなく描き直すため、絵柄が変わりやすい |

## See-through について
- 1 枚のアニメ絵を最大 23 の部位レイヤー（髪・顔・目・服・装飾など）に分解し、**隠れた部分も描き足した PSD** を出力する（SIGGRAPH 2026 論文、コードは Apache-2.0）。
- 必要な GPU: VRAM 12〜16GB（標準）、8GB でも量子化版で動く。**この作業環境には GPU が無いため、ここでは実行できない**。手元の PC か、クラウド GPU（RunPod など）か、公式のオンラインデモ（1 日の回数制限あり・低解像度）で実行する。
- 作者自身の位置づけは「Live2D 用 PSD の叩き台」。部位の分け方は意味（髪・目など）ごとで、Live2D 作家が動きを考えて分ける単位とは違う。フクロウ・タッセル・クリスタルのような細かい装飾は、手作業で分ける必要がある見込み。
- **商用利用の確認**: コードは Apache-2.0 だが、モデルの重み（Hugging Face で公開）のライセンスは README に書かれていない。この環境から Hugging Face に接続できず、確認できなかった。事業で使う前に、各重みのページでライセンスを確認すること。

## 参考
- See-through: https://github.com/shitagaki-lab/see-through
- Cubism 5.3 の新機能: https://docs.live2d.com/en/cubism-editor-manual/new-function5-3/
- Cubism 5.1 の新機能: https://docs.live2d.com/en/cubism-editor-manual/new-function5-1/
- Stretchy Studio: https://github.com/MangoLion/stretchystudio
- iki: https://github.com/zeikar/iki
