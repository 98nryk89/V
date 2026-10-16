"""Extract the original silver locks using traced regions and seeded GrabCut.

No image generation: segmentation selects source pixels. The annotation contains
hair cores, search envelopes, clothing exclusions and the narrow free tips.
Run after tools/refine_cutouts.py, from the repository root.
"""
import json
from pathlib import Path
import sys

import cv2
import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live2d_ai.decompose import poly_mask


def extract_long_hair(src, regions):
    h, w = src.shape[:2]
    yy, xx = np.mgrid[:h, :w]
    lab = cv2.cvtColor(src[..., :3], cv2.COLOR_BGR2LAB).astype(np.float32)
    core = np.maximum.reduce([poly_mask((h, w), p) for p in regions['cores']])
    envelope = np.maximum.reduce([poly_mask((h, w), p) for p in regions['envelopes']])
    cool_silver = np.clip((lab[..., 0] - 93) / 22, 0, 1) * np.clip((134 - lab[..., 2]) / 6, 0, 1)
    initial = np.maximum(core, envelope * cool_silver)
    shirt = (((xx > 460) & (xx < 555) & (yy > 600) & (yy < 865)) |
             ((xx > 610) & (xx < 687) & (yy > 580) & (yy < 860)) | (yy < 550))
    initial[shirt & (lab[..., 2] >= 126)] = 0
    protect = np.zeros((h, w), np.uint8)
    for points, width in regions['trim_lines']:
        cv2.polylines(protect, [np.array(points, np.int32)], False, 255, width, cv2.LINE_AA)
    initial *= 1 - (protect / 255) * (core < .5)
    envelope = ndi.binary_dilation(envelope > .05, iterations=28)
    gc = np.where(envelope & (yy >= 520), cv2.GC_PR_BGD, cv2.GC_BGD).astype(np.uint8)
    gc[initial > .4] = cv2.GC_PR_FGD
    seed = (ndi.binary_erosion(core > .95, iterations=5) & (lab[..., 0] > 130) &
            (lab[..., 2] < 125) & (yy >= 530))
    gc[seed] = cv2.GC_FGD
    gc[(protect > 20) & (core < .5)] = cv2.GC_BGD
    gc[shirt & (lab[..., 2] >= 126)] = cv2.GC_BGD
    cv2.setRNGSeed(0)
    cv2.grabCut(src[..., :3].copy(), gc, None, np.zeros((1, 65)), np.zeros((1, 65)),
                5, cv2.GC_INIT_WITH_MASK)
    matte = np.isin(gc, [cv2.GC_FGD, cv2.GC_PR_FGD]).astype(np.float32)
    for polygon in regions['trim_polygons']:
        matte *= 1 - poly_mask((h, w), polygon)
    labels, n = ndi.label(matte > .3, np.ones((3, 3)))
    keep = np.zeros(n + 1, bool)
    for x, y in [(420, 700), (740, 700), (340, 1100), (825, 1100)]:
        keep[labels[y, x]] = True
    keep[0] = False
    matte *= keep[labels]
    tips = np.zeros((h, w), np.uint8)
    for points in regions['curves']:
        cv2.polylines(tips, [np.array(points, np.int32)], False, 255, 4, cv2.LINE_AA)
    matte = np.maximum(matte, (tips / 255) * np.clip((lab[..., 0] - 105) / 30, 0, 1))
    # Dark shading at the roots is hair too; classifying only silver leaves
    # a stationary shadow strip and an abrupt horizontal edge below the ears.
    root = (core > .05) & (yy < 620) & (lab[..., 2] < 126)
    matte = np.maximum(matte, core * root)
    for polygon in regions['hair_tip_polygons']:
        matte = np.maximum(matte, (poly_mask((h, w), polygon) > .05) * (lab[..., 0] > 100))
    # Owl feathers are also silver; their silhouette belongs to the owl.
    matte[(xx < 375) & (yy < 660)] = 0
    return matte


def main():
    root = Path(__file__).resolve().parents[1]
    project = root / 'projects/owl_prince'
    src = cv2.imread(str(root / 'samples/ref12.png'), cv2.IMREAD_UNCHANGED)
    regions = json.loads((project / 'long_hair_regions.json').read_text())
    long = extract_long_hair(src, regions)
    head = cv2.imread(str(project / 'hair_head_clean_alpha.png'), 0) / 255
    h, w = head.shape
    yy, xx = np.mgrid[:h, :w]
    alpha = src[..., 3] / 255
    lab = cv2.cvtColor(src[..., :3], cv2.COLOR_BGR2LAB).astype(np.float32)
    face = cv2.imread(str(project / 'face_skin_mask.png'), 0) / 255
    # Above the owl/ears, every visible non-skin source pixel is head hair
    # or an ornament that a higher layer already owns. Do not restrict this
    # to the incomplete artist head mask's support.
    owl = poly_mask((h, w), [[150,480],[300,430],[345,470],[392,560],
                              [386,640],[345,735],[250,738],[145,708]])
    side_support = poly_mask((h, w), [
        [[330,400],[490,430],[480,610],[410,680],[373,650],[375,600],[355,560],[345,500]],
        [[650,425],[745,410],[780,610],[820,650],[750,650],[660,610]]])
    upper = (xx > 200) & (xx < 870) & (yy < 445) & ((face < .05) | (lab[..., 2] < 126))
    sides = (side_support > .5) & (lab[..., 2] < 126)
    head_support = (upper | sides) & (owl < .05)
    head_complete = np.where(head_support, alpha, head)
    head_complete[alpha < .015] = 0
    complete = np.maximum(head_complete, long)
    backing = cv2.imread(str(project / 'earring_hair_backing.png'), -1)[..., 3] / 255
    underlap = poly_mask((h, w), [
        [[421,470],[469,470],[500,570],[487,610],[435,610]],
        [[656,465],[713,465],[713,610],[642,610],[642,565]]]) * (backing > .1)
    for name, matte in [('hair_root_underlap', underlap), ('hair_long_alpha', long), ('hair_complete_alpha', complete),
                        ('hair_complete_extent', np.maximum(complete, backing))]:
        cv2.imwrite(str(project / f'{name}.png'), np.rint(matte * 255).astype(np.uint8))


if __name__ == '__main__':
    main()
