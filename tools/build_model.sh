#!/bin/sh
# 生成した差分を使って、モデルを作り直す（パーツ分け → 自動リグ → 差し替えパーツの追加 → 確認用の描画）。
#   必要: LAMA_WEIGHTS（big-lama.pt）、CHROME_PATH（Chromium）、art/gen/aligned_x2/（tools/gen_align.py の結果）
set -e
A=art/gen/aligned_x2
python3 tools/extract_parts.py art/work/upper_x2.png art/parts/upper \
  --feature-src "$A/eyenohair.png" --plate-src "$A/bagsaway.png"
python3 tools/build_gen_patches.py art/parts/upper
rm -rf art/parts/upper_s
python3 tools/scale_layers.py art/parts/upper art/parts/upper_s 0.85
tools/rig_and_render.sh art/parts/upper_s model/iki/base.iki model/iki/renders_s
python3 tools/add_gen_patches.py model/iki/base.iki art/parts/upper_s model/iki/model.iki
