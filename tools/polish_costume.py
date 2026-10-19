"""Refine only costume masks, join pixels and a complete tassel from existing art.

Run after extend_frame.py. No new face/hair artwork or physics-driver changes.
"""
import json
from pathlib import Path
import cv2
import numpy as np
from scipy import ndimage as ndi
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live2d_ai.decompose import poly_mask

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'projects/owl_prince'


def main():
    src=cv2.imread(str(ROOT/'samples/ref12.png'),-1)
    shape=src.shape[:2]
    r=json.loads((P/'costume_regions.json').read_text())
    for key,name in [('ribbon','ribbon_only_alpha'),('orn_chain','orn_chain_only_alpha'),('hang','hang_only_alpha')]:
        mask=poly_mask(shape,r[key])
        cv2.imwrite(str(P/(name+'.png')),np.rint(mask*255).astype(np.uint8))

    # Keep the original chain, gems and cap. Complete its skirt using the same
    # character's intact neighbouring tassel, instead of drawing a new design.
    origin=(995,950)
    canvas=np.zeros((580,110,4),np.uint8)
    hang=poly_mask(shape,r['hang'])
    lab=cv2.cvtColor(src[...,:3],cv2.COLOR_BGR2LAB)
    hsv=cv2.cvtColor(src[...,:3],cv2.COLOR_BGR2HSV)
    seed=(lab[...,0]>150)|((hsv[...,0]>98)&(hsv[...,0]<133)&(hsv[...,1]>90)&(hsv[...,2]>80))
    clean=ndi.binary_dilation(seed&(hang>.1),iterations=1)&(hang>.1)
    clean=ndi.binary_fill_holes(cv2.morphologyEx(clean.astype(np.uint8),cv2.MORPH_CLOSE,np.ones((3,3),np.uint8)))
    col=src.copy();col[...,3]=np.rint(col[...,3]*hang*clean).astype(np.uint8)
    canvas[:424,:110]=col[950:1374,995:1105]
    template=src[1172:1325,930:995].copy()
    poly=[[28,0],[37,0],[42,40],[57,135],[63,148],[52,151],[39,147],[27,151],[14,148],[3,141],[19,45]]
    mask=poly_mask(template.shape[:2],poly)
    template[...,3]=np.rint(template[...,3]*mask).astype(np.uint8)
    skirt=cv2.resize(template,(91,260),interpolation=cv2.INTER_CUBIC)
    # White neck at model (1041,1238). Full scalloped hem ends near y1498.
    yy,xx=288,0
    existing=canvas[yy:yy+260,xx:xx+91].astype(np.float32)
    fresh=skirt.astype(np.float32)
    blend=np.clip(np.arange(260,dtype=np.float32)/12,0,1)[:,None,None]
    # Once the new skirt is present, erase the truncated former skirt entirely.
    canvas[yy:]=0
    a=fresh[...,3:4]/255
    b=existing[...,3:4]/255*(1-blend)
    oa=a+b*(1-a)
    rgb=(fresh[...,:3]*a+existing[...,:3]*b*(1-a))/np.maximum(oa,.001)
    canvas[yy:yy+260,xx:xx+91]=np.dstack([rgb,oa[...,0]*255]).astype(np.uint8)
    cv2.imwrite(str(P/'tassel_full.png'),canvas)

    extension=cv2.imread(str(P/'frame_extension.png'),-1)
    y,x=np.mgrid[:extension.shape[0],:extension.shape[1]]
    wx=x-500;wy=y-50
    # Remove the stationary duplicate tassel/short-tassel ghost from the new art.
    patch=((wx>1001)&(wx<1100)&(wy>1220)&(wy<1533))|((wx>925)&(wx<1000)&(wy>1250)&(wy<1390))
    bright=extension[...,:3].max(2)>140
    remove=ndi.binary_dilation(patch&bright,iterations=3).astype(np.uint8)*255
    extension[...,:3]=cv2.inpaint(extension[...,:3],remove,9,cv2.INPAINT_TELEA)
    # Solve the join's colour transition using the existing costume as boundary
    # values. The face/core have zero extension alpha and are never replaced.
    target=extension[...,:3].copy()
    region=target[50:1424,500:1645]
    opaque=src[...,3]>250
    region[opaque]=src[...,:3][opaque]
    join_mask=(extension[...,3]>180).astype(np.uint8)*255
    join_mask=cv2.erode(join_mask,np.ones((3,3),np.uint8))
    bx,by,bw,bh=cv2.boundingRect(join_mask)
    extension[...,:3]=cv2.seamlessClone(extension[...,:3],target,join_mask,
                                     (bx+bw//2,by+bh//2),cv2.NORMAL_CLONE)
    cv2.imwrite(str(P/'frame_extension.png'),extension)


if __name__=='__main__':
    main()
