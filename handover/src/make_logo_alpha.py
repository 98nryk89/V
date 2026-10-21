"""ネームプレート(黒背景PNG)から背景を除去して透過PNG(logo.png)を作る。
使い方: python3 make_logo_alpha.py ../input/logo_original_black_bg.png logo.png
外周とつながった「ほぼ黒」の領域だけを背景として塗りつぶし判定するため、文字内側の暗い茶色は残る。"""
import sys
from collections import deque
import numpy as np
from PIL import Image, ImageFilter
src,dst=sys.argv[1],sys.argv[2]
im=Image.open(src).convert('RGB'); mx=np.array(im).max(2); H,W=mx.shape
dark=(mx<14); seen=np.zeros_like(dark); dq=deque()
for x in range(W):
    for y in (0,H-1):
        if dark[y,x] and not seen[y,x]: seen[y,x]=True; dq.append((y,x))
for y in range(H):
    for x in (0,W-1):
        if dark[y,x] and not seen[y,x]: seen[y,x]=True; dq.append((y,x))
while dq:
    y,x=dq.popleft()
    for ny,nx in ((y+1,x),(y-1,x),(y,x+1),(y,x-1)):
        if 0<=ny<H and 0<=nx<W and dark[ny,nx] and not seen[ny,nx]:
            seen[ny,nx]=True; dq.append((ny,nx))
al=Image.fromarray(((~seen)*255).astype(np.uint8)).filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(1.0))
out=im.copy(); out.putalpha(al); out.save(dst)
