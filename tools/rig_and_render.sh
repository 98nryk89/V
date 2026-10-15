#!/bin/sh
# 役割別レイヤー → iki の自動リグ → ポーズ別の描画。リポジトリのルートで実行する。
#   使い方: tools/rig_and_render.sh [レイヤーのフォルダ] [出力 .iki] [描画の出力フォルダ]
# 環境変数 CHROME_PATH に Chromium の実行ファイル（root では --no-sandbox 付きのラッパー）を指定する。
set -e
L="${1:-art/parts/upper}"
OUT="${2:-model/iki/upper.iki}"
R="${3:-model/iki/renders}"
mkdir -p "$(dirname "$OUT")" "$R"
LAYERS=""
for role in face eye_L eye_R iris_L iris_R lash_L lash_R brow_L brow_R mouth mouth_open hair_back hair_front body; do
  [ -f "$L/$role.png" ] && LAYERS="$LAYERS{\"path\":\"$L/$role.png\"},"
done
LAYERS="[${LAYERS%,}]"
node iki/call.mjs auto_rig_from_layers "{\"layers\":$LAYERS,\"outputPath\":\"$OUT\"}" | cut -c1-400
rm -f "$R"/*.png
node iki/call.mjs render_poses "{\"modelPath\":\"$OUT\",\"outDir\":\"$R\"}" | grep -v "^/" | cut -c1-400 || true
