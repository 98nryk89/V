"""Rebuild local cutout masks from the existing artist/source pixels (no regeneration).

Run from the repository root: python tools/refine_cutouts.py
"""
from pathlib import Path
import sys

import cv2
import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live2d_ai.decompose import poly_mask, push_pull_fill


def refine_hair(source_alpha, artist_alpha, face_mask, lab):
    support = ndi.binary_dilation(artist_alpha > .02, iterations=3)
    # Outside the skin, a hair outline must carry the source's own coverage;
    # keeping the difference on body leaves a stationary duplicate when it moves.
    certain = support & ((face_mask < .05) | (lab[..., 2] < 126))
    matte = np.where(certain, source_alpha, artist_alpha)
    matte = np.minimum(matte, source_alpha)
    matte[source_alpha < .015] = 0
    labels, count = ndi.label(matte > .025, structure=np.ones((3, 3), bool))
    if count:
        areas = np.bincount(labels.ravel())
        keep = areas >= 6
        keep[0] = False
        matte = np.where(keep[labels], matte, 0)
    return matte.astype(np.float32)


def main():
    root = Path(__file__).resolve().parents[1]
    proj = root / 'projects/owl_prince'
    src = cv2.imread(str(root / 'samples/ref12.png'), cv2.IMREAD_UNCHANGED)
    alpha = src[..., 3].astype(np.float32) / 255
    rgb = src[..., 2::-1]
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    artist = cv2.imread(str(proj / 'hair_head_alpha.png'), 0).astype(np.float32) / 255
    face = cv2.imread(str(proj / 'face_skin_mask.png'), 0).astype(np.float32) / 255
    matte = refine_hair(alpha, artist, face, lab)
    cv2.imwrite(str(proj / 'hair_head_clean_alpha.png'), np.rint(matte * 255).astype(np.uint8))

    ear_r = cv2.imread(str(proj / 'ear_R_mask.png'), 0).astype(np.float32) / 255
    cv2.imwrite(str(proj / 'ear_R_rigid_mask.png'), ((ear_r > .2) * 255).astype(np.uint8))
    face_extent = cv2.imread(str(proj / 'face_skin_extent.png'), 0).astype(np.float32) / 255
    face_extent *= 1 - (ear_r > .2)
    cv2.imwrite(str(proj / 'face_skin_extent_separate_ear.png'), np.rint(face_extent * 255).astype(np.uint8))

    h, w = alpha.shape
    yy, xx = np.mgrid[:h, :w]
    # Trace the actual metal/jewel contour; a dark-colour gate also takes
    # the neighbouring grey hair and even the strand below the pendant.
    contour = [[424,448],[428,450],[429,455],[426,462],[428,466],[427,471],
               [425,473],[426,479],[430,483],[436,489],[429,496],[427,501],
               [429,505],[432,510],[434,520],[436,526],[431,539],[427,549],
               [426,552],[427,556],[432,560],[427,565],[426,570],[426,576],
               [423,580],[420,577],[420,573],[422,569],[421,566],[415,562],
               [416,558],[421,555],[421,550],[417,545],[412,534],[409,525],
               [412,515],[416,506],[420,502],[419,498],[414,494],[411,489],
               [417,482],[421,479],[421,473],[418,470],[418,465],[421,461],
               [419,457],[420,451]]
    left = poly_mask((h,w), contour)
    cv2.imwrite(str(proj / 'earring_L_mask.png'), np.rint(left * 255).astype(np.uint8))
    right = cv2.imread(str(proj / 'earring_R_mask.png'), 0).astype(np.float32) / 255

    # Under the hoop, borrow only silver-hair colours; never skin, jewels or jacket.
    ref = np.zeros_like(src)
    backing = np.zeros((h, w), np.float32)
    closed_figure = ndi.binary_closing(alpha > .5, iterations=6)
    for centre, mask, top in [(424, left, 476), (699, right, 466)]:
        roi = (np.abs(xx - centre) <= 55) & (yy >= 445) & (yy <= 650)
        silver = roi & (alpha > .9) & (lab[..., 0] > 110) & (lab[..., 2] >= 115) & (lab[..., 2] <= 128)
        silver &= ~ndi.binary_dilation(mask > .05, iterations=5)
        silver = ndi.binary_erosion(silver, iterations=1)
        if silver.sum() < 20:
            raise ValueError('not enough uncontaminated silver hair for earring backing')
        colour = push_pull_fill(rgb, silver)
        under = (np.abs(xx - centre) <= 60) & (yy >= top - 22) & (yy <= 650) & (alpha > .5)
        gap = (np.abs(xx - centre) <= 24) & (yy >= top - 5) & (yy <= top + 125) & closed_figure
        under_a = cv2.GaussianBlur((under | gap).astype(np.float32), (0,0), .7)
        valid = under_a > .001
        backing = np.maximum(backing, under_a)
        ref[valid, :3] = np.clip(colour[valid, ::-1], 0, 255).astype(np.uint8)
        ref[valid, 3] = np.rint(under_a[valid] * 255).astype(np.uint8)
    cv2.imwrite(str(proj / 'earring_hair_backing.png'), ref)
    extent = poly_mask((h, w), [[0, 545], [w, 545], [w, h], [0, h]])
    extent = np.maximum(extent, backing)
    cv2.imwrite(str(proj / 'body_hair_extent.png'), np.rint(extent * 255).astype(np.uint8))


if __name__ == '__main__':
    main()
