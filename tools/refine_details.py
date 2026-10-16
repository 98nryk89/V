"""Small, reversible source-pixel corrections on top of the accepted hair matte."""
from pathlib import Path
import sys
import cv2
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live2d_ai.decompose import poly_mask, push_pull_fill
from scipy import ndimage as ndi


def main():
    root = Path(__file__).resolve().parents[1]
    p = root / 'projects/owl_prince'
    src = cv2.imread(str(root / 'samples/ref12.png'), -1)
    lab = cv2.cvtColor(src[..., :3], cv2.COLOR_BGR2LAB).astype(np.float32)
    complete = cv2.imread(str(p / 'hair_complete_alpha.png'), 0) / 255
    extent = cv2.imread(str(p / 'hair_complete_extent.png'), 0) / 255
    shape = complete.shape
    # Only the thin eyebrow strokes, never a rectangular eyebrow/hair patch.
    brows = poly_mask(shape, [
        [[435,344],[459,344],[485,346],[514,350],[520,354],[509,356],[482,352],[456,351],[435,351]],
        [[594,343],[615,338],[638,333],[661,329],[669,333],[654,339],[633,343],[612,348],[594,351]]])
    # Brows seen through the bangs belong to face; the artist's actual hair
    # must never be sliced horizontally along the brow protection polygon.
    artist_hair = cv2.imread(str(p / 'hair_head_alpha.png'), 0) / 255
    brows *= artist_hair < .02
    collar = poly_mask(shape, [
        [[477,589],[500,606],[541,630],[547,650],[521,668],[487,643]],
        [[647,595],[674,573],[682,634],[653,657],[621,642],[631,622]]])
    # Keep the cool silver strands over the collar; return black cloth and white
    # collar pixels to body, so they cannot be carried over the white lapels.
    collar *= ((lab[..., 0] < 120) | (lab[..., 2] >= 126))
    protect = np.maximum(brows > .1, collar > .1)
    detailed = np.where(protect, 0, complete)
    detailed_extent = np.where(protect, 0, extent)
    zones = {
        'L': [[328,1006],[335,1010],[320,1036],[299,1056],[273,1074],[246,1082],
              [221,1082],[207,1074],[231,1074],[255,1064],[278,1048],[300,1028]],
        'R': [[784,1079],[788,1097],[777,1118],[758,1137],[737,1148],[716,1152],
              [693,1147],[719,1145],[739,1134],[756,1117],[769,1094]],
    }
    for side, polygon in zones.items():
        tip = (poly_mask(shape, polygon) > .1) * (detailed > .1)
        # Full ownership at the tip: do not leave its pale edge on the base.
        cv2.imwrite(str(p / f'hair_tip_{side}_alpha.png'), (tip * 255).astype(np.uint8))
        detailed_extent[tip] = 0
    # The neck can uncover the upper collar at the angle limits. Reconstruct
    # just the hidden white overlap from clean original collar pixels.
    yy, xx = np.mgrid[:shape[0], :shape[1]]
    collar_roi = (xx > 485) & (xx < 665) & (yy > 575) & (yy < 670)
    white = collar_roi & (lab[..., 0] > 180) & (lab[..., 1] < 134) & (lab[..., 2] >= 124) & (lab[..., 2] < 130)
    under = ndi.binary_dilation(white, iterations=18) & (yy < 649) & (yy > 555) & (xx > 475) & (xx < 680)
    neck = poly_mask(shape, [[478,470],[672,470],[674,556],[662,584],[640,604],
                              [600,624],[575,636],[545,616],[505,587],[486,566],[480,540]])
    # The coarse neck polygon also contains hair and the standing collar.
    # Only source skin may become a newly revealed white collar underlap.
    skin = (lab[..., 2] >= 130) & (lab[..., 1] >= 130) & (lab[..., 0] > 130)
    # Two source pixels of underlap also cover the antialiased skin edge.
    under &= (neck > .5) & ndi.binary_dilation(skin, iterations=2)
    colour = push_pull_fill(src[..., :3], white)
    ref = np.dstack([colour, under.astype(np.float32) * 255]).astype(np.uint8)
    cv2.imwrite(str(p / 'collar_underlap.png'), ref)
    base = poly_mask(shape, [[0,610],[1145,610],[1145,1374],[0,1374]])
    cv2.imwrite(str(p / 'body_detail_extent.png'), np.rint(np.maximum(base, under) * 255).astype(np.uint8))
    for name, a in [('hair_detail_alpha', detailed), ('hair_detail_extent', detailed_extent),
                    ('brow_protect_alpha', (brows > .1).astype(float))]:
        cv2.imwrite(str(p / f'{name}.png'), np.rint(a * 255).astype(np.uint8))


if __name__ == '__main__':
    main()
