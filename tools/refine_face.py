"""Remove the occluded duplicate jaw stroke from the neck backing only."""
from pathlib import Path
import cv2
import numpy as np
from scipy import ndimage as ndi


def main():
    root = Path(__file__).resolve().parents[1]
    p = root / 'projects/owl_prince'
    src = cv2.imread(str(root / 'samples/ref12.png'), -1)
    face = cv2.imread(str(p / 'face_skin_mask.png'), 0) > 127
    yy, xx = np.mgrid[:face.shape[0], :face.shape[1]]
    # The lower boundary of the supplied face matte, not a polygon edge.
    lower = np.where(face & (yy > 440) & (yy < 580), yy, 0).max(axis=0)
    band = (np.abs(yy-lower[None,:]) <= 5) & (lower[None,:] > 470) & (xx > 478) & (xx < 675)
    lab = cv2.cvtColor(src[..., :3], cv2.COLOR_BGR2LAB)
    # Sample only neck skin below the original jaw, preserving its shading.
    seeds = (yy > lower[None,:]+7) & (yy < lower[None,:]+24) & (xx > 485) & (xx < 665) & (lower[None,:] > 470)
    seeds &= (lab[...,0] > 120) & (lab[...,1] >= 132) & (lab[...,2] >= 129)
    if seeds.sum() < 20:
        raise ValueError("neck backing needs clean skin below the jaw")
    _, indices = ndi.distance_transform_edt(~seeds, return_indices=True)
    rgb = src[..., :3][indices[0],indices[1]]
    a = cv2.GaussianBlur(band.astype(np.float32), (0,0), .8)
    cv2.imwrite(str(p / 'neck_underjaw.png'), np.dstack([rgb,np.rint(a*255).astype('uint8')]))


if __name__ == '__main__':
    main()
