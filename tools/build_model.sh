#!/bin/sh
# 元の絵を土台にしたモデルを作る（現在の方式）。
#   1. 生成した差分を作業キャンバスに位置合わせ（初回のみ。重み: RealESRGAN_x4plus_anime_6B.pth）
#   2. 土台＋重ね用パーツ＋頭の動きの変形をまとめて model/iki/overlay.iki を作る
# 使い方: ESRGAN_WEIGHTS=...pth tools/build_model.sh
set -e
if [ ! -d art/gen/aligned_x2 ] || [ -z "$(ls art/gen/aligned_x2/*.png 2>/dev/null)" ]; then
  python3 tools/gen_align.py --weights "${ESRGAN_WEIGHTS:?ESRGAN_WEIGHTS に RealESRGAN_x4plus_anime_6B.pth のパスを指定してください}"
fi
python3 tools/build_overlay_model.py --out model/iki/overlay.iki
