#!/bin/sh
# 顔まわりの切り抜きを、表情・向き別に描画する（確認用）。使い方: tools/render_faces.sh model.iki 出力フォルダ x y w h
M="$1"; O="$2"; X="${3:-660}"; Y="${4:-255}"; W="${5:-612}"; H="${6:-646}"
mkdir -p "$O"; rm -f "$O"/*.png
C="\"crop\":{\"x\":$X,\"y\":$Y,\"w\":$W,\"h\":$H}"
node iki/call.mjs render_poses "{\"modelPath\":\"$M\",\"outDir\":\"$O\",\"poses\":[
{\"name\":\"a_rest\",\"values\":{},$C},
{\"name\":\"b_smile\",\"values\":{\"ParamMouthForm\":1,\"ParamBrowLY\":0.25,\"ParamBrowRY\":0.25},$C},
{\"name\":\"c_angry\",\"values\":{\"ParamBrowLY\":-0.5,\"ParamBrowRY\":-0.5,\"ParamBrowLAngle\":0.8,\"ParamBrowRAngle\":-0.8,\"ParamMouthForm\":-0.9},$C},
{\"name\":\"d_sad\",\"values\":{\"ParamBrowLY\":0.35,\"ParamBrowRY\":0.35,\"ParamBrowLAngle\":-0.8,\"ParamBrowRAngle\":0.8,\"ParamMouthForm\":-0.8},$C},
{\"name\":\"e_surprised\",\"values\":{\"ParamBrowLY\":0.8,\"ParamBrowRY\":0.8,\"ParamMouthOpenY\":0.9},$C},
{\"name\":\"f_turnX30\",\"values\":{\"ParamAngleX\":30},$C},
{\"name\":\"g_turnXm30\",\"values\":{\"ParamAngleX\":-30},$C},
{\"name\":\"h_up30\",\"values\":{\"ParamAngleY\":30},$C},
{\"name\":\"i_down30\",\"values\":{\"ParamAngleY\":-30},$C},
{\"name\":\"j_blink\",\"values\":{\"ParamEyeLOpen\":0,\"ParamEyeROpen\":0},$C}
]}" | grep -v "^/" | cut -c1-200
python3 - "$O" <<'PY'
import sys, glob
from PIL import Image
fs=sorted(glob.glob(sys.argv[1]+'/*.png')); ims=[Image.open(f).convert('RGB') for f in fs]
w,h=ims[0].size; sc=0.5
t=[i.resize((int(w*sc),int(h*sc)), Image.LANCZOS) for i in ims]
W,H=t[0].size
m=Image.new('RGB',(W*5,H*2),(30,30,30))
for k,i in enumerate(t): m.paste(i,((k%5)*W,(k//5)*H))
m.save(sys.argv[1]+'/_montage.jpg', quality=92)
PY
