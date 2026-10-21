#!/usr/bin/env bash
# 全工程を最初から再現するスクリプト。src/ で実行する。 必要: python3(numpy, Pillow), ffmpeg
set -euo pipefail
ANIME=../input/anime_original.mp4          # 元のアニメ動画(60秒)
OUT=../build; mkdir -p $OUT

# 1) ロゴ透過 → 2) 音声(音楽+効果音) → 3) 映像(文字あり/なし) → 4) 文字PNG
[ -f logo.png ] || python3 make_logo_alpha.py ../input/logo_original_black_bg.png logo.png
python3 audio2.py                                   # open.wav trailer2.wav trailer_music.wav trailer_sfx.wav endcard.wav
python3 render2.py open open_v.mp4                  # 冒頭カード(文字あり) 5.4s
python3 render2.py trailer trailer2_v.mp4           # 予告編(文字あり)   20.4s
NOTEXT=1 python3 render2.py open open_notext_v.mp4
NOTEXT=1 python3 render2.py trailer trailer_notext_v.mp4
python3 overlays.py                                 # ov/*.png (文字だけの透過PNG)

# 5) 区間ごとのmp4
E="-c:v libx264 -crf 16 -preset medium -pix_fmt yuv420p -c:a aac -b:a 192k -ar 44100 -movflags +faststart"
ffmpeg -y -i open_v.mp4 -i open.wav -map 0:v -map 1:a $E -shortest $OUT/00_opening_card.mp4
ffmpeg -y -i $ANIME -t 58.4 $E $OUT/01_anime_main.mp4                      # 58.4秒で切る=神ゲーカンパニー！カードの直前
ffmpeg -y -i trailer2_v.mp4 -i trailer2.wav -af volume=-3dB -map 0:v -map 1:a $E -shortest $OUT/02_trailer.mp4
ffmpeg -y -ss 58.6 -t 1.2 -i $ANIME -i endcard.wav -filter_complex \
 "[0:v]setpts=PTS-STARTPTS,fps=30,loop=loop=2:size=36:start=0,fade=t=in:st=0:d=0.5:color=0xFCF3E0[v]" \
 -map "[v]" -map 1:a $E -shortest $OUT/03_endcard_kamige.mp4                # 点滅(0.6秒周期)の2周期分を3回ループ=3.6秒

# 6) 結合(完成版)
ffmpeg -y -i $OUT/00_opening_card.mp4 -i $OUT/01_anime_main.mp4 -i $OUT/02_trailer.mp4 -i $OUT/03_endcard_kamige.mp4 -filter_complex \
 "[1:v]fade=t=in:st=0:d=0.5,fade=t=out:st=58.0:d=0.4[v1];[1:a]afade=t=in:st=0:d=0.3,afade=t=out:st=58.0:d=0.4[a1];\
  [0:v][0:a][v1][a1][2:v][2:a][3:v][3:a]concat=n=4:v=1:a=1[v][a]" -map "[v]" -map "[a]" $E $OUT/mukachi_kachi_trailer_v3.mp4

# 7) ブラウザ編集画面(editor.html)用の軽量素材 → ed/media/ (editor.htmlと一緒に公開する)
mkdir -p ed/media
VE="-an -c:v libx264 -crf 21 -preset slow -g 15 -pix_fmt yuv420p -r 30 -movflags +faststart"
AE="-vn -c:a libmp3lame -b:a 192k -ar 44100 -ac 2"
ffmpeg -y -i open_notext_v.mp4 $VE ed/media/open.mp4
ffmpeg -y -i $ANIME -an -c:v libx264 -crf 29 -preset slow -g 15 -pix_fmt yuv420p -r 30 -movflags +faststart ed/media/anime.mp4
ffmpeg -y -i trailer_notext_v.mp4 -an -c:v libx264 -crf 25 -preset slow -g 15 -pix_fmt yuv420p -r 30 -movflags +faststart ed/media/trailer.mp4
ffmpeg -y -ss 58.6 -t 1.2 -i $ANIME -vf "setpts=PTS-STARTPTS,fps=30,loop=loop=2:size=36:start=0" $VE ed/media/card.mp4
ffmpeg -y -i open.wav $AE ed/media/open.mp3;  ffmpeg -y -i $ANIME $AE ed/media/anime.mp3
ffmpeg -y -i trailer_music.wav $AE ed/media/trailer_music.mp3; ffmpeg -y -i trailer_sfx.wav $AE ed/media/trailer_sfx.mp3
ffmpeg -y -i endcard.wav $AE ed/media/card.mp3
echo "done -> $OUT"
