"""Separate existing iris pixels and fill only the white hidden behind them."""
from pathlib import Path
import json
import cv2
import numpy as np
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live2d_ai.decompose import poly_mask
from scipy import ndimage as ndi


def main():
    root = Path(__file__).resolve().parents[1]
    p = root / 'projects/owl_prince'
    normal = cv2.imread(str(root / 'samples/ref12.png'), -1)[..., :3]
    surprised = cv2.imread(str(root / 'samples/surprised_ref.png'))
    shape = normal.shape[:2]
    aperture = {
        'L': [[434,381],[448,374],[465,371],[478,368],[490,368],[506,371],[526,382],[522,396],[503,401],[479,402],[454,394]],
        'R': [[590,373],[605,364],[619,359],[632,358],[646,359],[662,362],[682,372],[675,387],[650,392],[625,393],[604,386]],
    }
    normal_opening = {
        'L': [[447,383],[460,377],[480,374],[501,376],[518,383],[519,388],[506,391],[490,394],[472,394],[455,389]],
        'R': [[605,378],[619,372],[639,369],[658,368],[677,373],[682,379],[671,384],[652,387],[632,387],[615,384]],
    }
    eyes = {'L': ([485.5,384,26,14], [483.5,382,17.5,17.5]),
            'R': ([632,379,21,14], [631.5,373.5,17,17])}
    refs = {key: np.zeros((*shape,4), np.uint8) for key in ['normal','surprise']}
    regions = {}
    for side, ellipses in eyes.items():
        for kind, src, (cx,cy,rx,ry) in zip(['normal','surprise'], [normal,surprised], ellipses):
            opening = normal_opening[side] if kind=='normal' else aperture[side]
            open_a = poly_mask(shape, opening)
            ellipse = poly_mask(shape, {'ellipse':[cx,cy,rx,ry,0]})
            iris = np.minimum(ellipse, open_a)
            roi = [int(cx-48),int(cy-30),int(cx+49),int(cy+31)]
            x0,y0,x1,y1 = roi
            image = src[y0:y1,x0:x1]
            a = iris[y0:y1,x0:x1]
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            cover = cv2.dilate((a>.01).astype('uint8'),np.ones((5,5),np.uint8))>0
            seed_cover = cover
            if kind=='normal':
                # The moving crop includes a white margin. It must not exclude
                # those same original white pixels from the fill's colour seeds.
                core = poly_mask(shape, {'ellipse':[cx,cy,max(rx-8,12),ry+1,0]})
                seed_cover = core[y0:y1,x0:x1]>.1
            seeds = (open_a[y0:y1,x0:x1]>.8) & ~seed_cover
            seeds &= (lab[...,0]>185) & (lab[...,1]<143) & (lab[...,2]>123)
            if seeds.sum()<15:
                raise ValueError(f'{kind} eye {side} needs neighbouring white pixels')
            # Very sparse white seeds do not reach the centre of a small
            # push-pull pyramid. Nearest white colours provide a complete
            # backing, then a small blur blends their shading under the iris.
            _, indices = ndi.distance_transform_edt(~seeds, return_indices=True)
            white = image[indices[0],indices[1]].astype(np.float32)
            white = cv2.GaussianBlur(white,(0,0),4)
            alpha = ((a>.1).astype(np.float32) if kind=='normal' else cover.astype(np.float32)*open_a[y0:y1,x0:x1])
            refs[kind][y0:y1,x0:x1,:3] = np.clip(white,0,255).astype('uint8')
            refs[kind][y0:y1,x0:x1,3] = np.rint(alpha*255).astype('uint8')
            if kind=='normal':
                cv2.imwrite(str(p/f'iris_{side}_alpha.png'),np.rint(iris*255).astype('uint8'))
                regions.setdefault(side,{})['normal_opening']=opening
            else:
                contours,_=cv2.findContours((iris>.5).astype('uint8'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
                contour=cv2.approxPolyDP(max(contours,key=cv2.contourArea),.25,True).reshape(-1,2).tolist()
                regions[side].update(iris=contour,opening=opening)
    for kind, ref in refs.items():
        cv2.imwrite(str(p/f'{kind}_eye_white_backing.png'),ref)
    (p/'gaze_regions.json').write_text(json.dumps(regions,indent=1)+'\n')


if __name__ == '__main__':
    main()
