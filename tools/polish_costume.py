"""Refine only costume masks, join pixels and a complete tassel from existing art.

Run after extend_frame.py. No new face/hair artwork or physics-driver changes.
"""
import json
from pathlib import Path
import cv2
import numpy as np
from scipy import ndimage as ndi
from scipy.interpolate import PchipInterpolator
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live2d_ai.decompose import poly_mask

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'projects/owl_prince'


def ribbon_tip_underlap(src):
    """Continue local strand gradients, anchored to the original silver hair.

    The outside is a smooth continuation of the visible contour. A small Poisson
    solve matches the donor's strand detail to the actual hair on the inner and
    lower joins; empty background does not impose a black boundary condition.
    """
    h,w=src.shape[:2]
    ys=np.arange(520,611,dtype=float)
    outer=PchipInterpolator([520,535,550,565,580,595,610],
                            [733,737,741,744,748,752,758])(ys)
    points=np.vstack([np.c_[outer,ys],[[714,610],[714,520]]])
    large=np.zeros((h*4,w*4),np.uint8)
    cv2.fillPoly(large,[np.rint(points*4).astype(np.int32)],255)
    matte=cv2.resize(large,(w,h),interpolation=cv2.INTER_AREA).astype(float)/255
    # Only use uncontaminated, opaque silver hair as boundary pixels.
    hsv=cv2.cvtColor(src[...,:3],cv2.COLOR_BGR2HSV)
    lab=cv2.cvtColor(src[...,:3],cv2.COLOR_BGR2LAB)
    support=matte>0
    clean=support&(src[...,3]>240)&(hsv[...,1]<65)&(lab[...,0]>110)
    clean=ndi.binary_erosion(clean,iterations=1)
    unknown=support&~clean
    yy,xx=np.mgrid[:h,:w]
    donor=src[yy,np.maximum(xx-18,0),:3].astype(float)
    # Solve u-donor with zero normal derivative at the outside hair silhouette.
    # At the original hair, its RGB provides a Dirichlet boundary condition.
    indices=np.full((h,w),-1,int);indices[unknown]=np.arange(unknown.sum())
    rows=[];cols=[];values=[];rhs=np.zeros((unknown.sum(),3))
    for y,x in zip(*np.nonzero(unknown)):
        i=indices[y,x];degree=0
        for dy,dx in [(0,-1),(0,1),(-1,0),(1,0)]:
            ny,nx=y+dy,x+dx
            if not(0<=ny<h and 0<=nx<w and support[ny,nx]):continue
            degree+=1;rhs[i]+=donor[y,x]-donor[ny,nx]
            if unknown[ny,nx]:
                rows.append(i);cols.append(indices[ny,nx]);values.append(-1)
            else:rhs[i]+=src[ny,nx,:3]
        rows.append(i);cols.append(i);values.append(degree)
    matrix=coo_matrix((values,(rows,cols)),shape=(unknown.sum(),unknown.sum())).tocsr()
    colour=src[...,:3].copy()
    colour[unknown]=np.rint(np.clip(spsolve(matrix,rhs),0,255)).astype(np.uint8)
    return matte,colour


def main():
    src=cv2.imread(str(ROOT/'samples/ref12.png'),-1)
    shape=src.shape[:2]
    r=json.loads((P/'costume_regions.json').read_text())
    for key,name in [('ribbon','ribbon_only_alpha'),('orn_chain','orn_chain_only_alpha'),('hang','hang_only_alpha')]:
        mask=poly_mask(shape,r[key])
        cv2.imwrite(str(P/(name+'.png')),np.rint(mask*255).astype(np.uint8))

    # Only the source metal links and gem contours belong to the hanging chain.
    # Purple ribbon patterns inside the old broad chain envelope are not links.
    lab=cv2.cvtColor(src[...,:3],cv2.COLOR_BGR2LAB)
    gems=np.maximum.reduce([poly_mask(shape,points) for points in r['chain_gems']])
    links=np.maximum.reduce([poly_mask(shape,points) for points in r['chain_links']])
    metal=np.clip((lab[...,0].astype(float)-110)/35,0,1)
    chain=np.maximum(gems,links*metal)
    cv2.imwrite(str(P/'orn_chain_only_alpha.png'),np.rint(chain*255).astype(np.uint8))
    # The original artist hair mask also contains the ornament. Return leftover
    # purple/gold cloth pixels to the ribbon, not to hair or the stationary body.
    yy,xx=np.mgrid[:shape[0],:shape[1]]
    hsv=cv2.cvtColor(src[...,:3],cv2.COLOR_BGR2HSV)
    skin=cv2.imread(str(P/'face_skin_mask.png'),0)>10
    ear=cv2.imread(str(P/'ear_R_rigid_mask.png'),0)>10
    roi=(xx>735)&(xx<880)&(yy>275)&(yy<630)&~skin&~ear
    ornament=(hsv[...,1]>85)|((lab[...,2]>126)&(lab[...,0]>65))
    ornament|=(xx>750)&(xx<805)&(yy>300)&(lab[...,0]<85)
    extra=roi&ornament&(src[...,3]>0)
    # The source cloth edge sits 1-3px outside the older polygon at the tip.
    # Its dark purple rim belongs to the ribbon, never to the silver underlap.
    rim=poly_mask(shape,[[739,515],[742,515],[741,540],[740,561],
                         [738,576],[732,576],[733,552],[735,530]])
    extra|=(rim>.1)&(hsv[...,1]>70)&(src[...,3]>0)
    ribbon=np.maximum(poly_mask(shape,r['ribbon']),extra.astype(np.float32))
    cv2.imwrite(str(P/'ribbon_only_alpha.png'),np.rint(ribbon*255).astype(np.uint8))
    # Do not reconstruct a hair-coloured silhouette under a moving ornament.
    no_fill=poly_mask(shape,[[730,270],[905,270],[905,665],[730,665]])
    # A short hair strand continues underneath the lowest front fold. Keep
    # that underlap attached to the real hair; the rest of the cloth stays empty.
    tip_hair,tip_colour=ribbon_tip_underlap(src)
    # Retain the existing ear underlap in the same reference image.
    backing=cv2.imread(str(P/'earring_hair_backing.png'),-1)
    backing[no_fill>.5]=0  # no legacy flat ear backing behind this ornament
    tip=tip_hair>0
    backing[tip,:3]=tip_colour[tip]
    backing[tip,3]=np.rint(tip_hair[tip]*255).astype(np.uint8)
    cv2.imwrite(str(P/'ornament_tip_hair_backing.png'),backing)
    hair_no_fill=no_fill*(1-tip_hair)
    cv2.imwrite(str(P/'ornament_no_backfill.png'),np.rint(hair_no_fill*255).astype(np.uint8))
    body_no_fill=np.maximum(no_fill,poly_mask(shape,[[806,560],[960,560],[960,700],[806,700]]))
    cv2.imwrite(str(P/'body_no_backfill.png'),np.rint(body_no_fill*255).astype(np.uint8))
    # Fill only the hidden costume beneath tassels with nearby dark cloth, not
    # with white fibres left at the edge of their former position.
    specs=json.loads((P/'parts_spec.json').read_text())['parts']
    zone=np.zeros(shape,np.float32)
    for part in specs:
        if part['id'] in ['tasselL','tasselR1','tasselR2']:
            zone=np.maximum(zone,poly_mask(shape,part['zone']))
    zone=np.maximum(zone,poly_mask(shape,r['hang']))
    target=ndi.binary_dilation(zone>.1,iterations=3)
    nearby=ndi.binary_dilation(target,iterations=35)
    known=nearby&(lab[...,0]<130)&(src[...,3]>240)&~target
    _,indices=ndi.distance_transform_edt(~known,return_indices=True)
    cloth=src[...,:3][indices[0],indices[1]]
    cloth=cv2.GaussianBlur(cloth,(0,0),1)
    backing=cv2.imread(str(P/'collar_underlap.png'),-1)
    backing[target,:3]=cloth[target]
    backing[target,3]=255
    cv2.imwrite(str(P/'costume_body_backing.png'),backing)

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
    skirt=cv2.resize(template,(91,260),interpolation=cv2.INTER_LANCZOS4)
    # A mild local sharpen restores fibres softened by enlargement; keep alpha
    # edges narrow so the skirt has no translucent glowing border.
    detail=skirt[...,:3].astype(np.float32)
    detail=np.clip(detail+.5*(detail-cv2.GaussianBlur(detail,(0,0),.65)),0,255)
    skirt[...,:3]=detail.astype(np.uint8)
    coverage=skirt[...,3].astype(np.float32)/255
    coverage=np.clip((coverage-.12)/.76,0,1)
    skirt[...,3]=np.rint(coverage*255).astype(np.uint8)
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
