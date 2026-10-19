"""Attach only the outer sleeves and lower costume from supplied wider artwork.

Local similarity fits were measured with SIFT/RANSAC on each sleeve and lower
costume. Fixed matrices are recorded in frame_extension_regions.json for repeatable
output. Does not regenerate artwork or alter any original source/mask.
"""
import json
from pathlib import Path

import cv2
import numpy as np
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'projects/owl_prince'


def smooth(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def make_extension():
    ref = cv2.imread(str(ROOT / 'samples/wide_frame_ref.png'))
    cfg = json.loads((PROJECT / 'frame_extension_regions.json').read_text())
    # Remove only connected white background; keep enclosed white costume details.
    white = ref.min(2) > 235
    labels, _ = ndi.label(white)
    border_ids = np.unique(np.r_[labels[0], labels[-1], labels[:, 0], labels[:, -1]])
    background = np.isin(labels, border_ids[border_ids > 0])
    labels, _ = ndi.label(~background)
    sizes = np.bincount(labels.ravel())
    foreground = labels == (1 + np.argmax(sizes[1:]))
    foreground = ndi.binary_fill_holes(foreground)
    alpha = foreground.astype(np.float32)
    near = ndi.binary_dilation(foreground, iterations=1) & ~foreground
    alpha[near] = np.clip((255 - ref.min(2)[near]) / 30, 0, 1)
    rgba = np.dstack([ref, alpha * 255]).astype(np.uint8)

    # Retain the original model's coordinates. This canvas may extend outside it.
    origin = cfg['origin']
    yy, xx = np.mgrid[:cfg['shape'][0], :cfg['shape'][1]].astype(np.float32)
    xx += origin[0]
    yy += origin[1]
    maps = []
    for matrix in cfg['matrices']:
        inv = cv2.invertAffineTransform(np.array(matrix))
        maps.append((inv[0, 0] * xx + inv[0, 1] * yy + inv[0, 2],
                     inv[1, 0] * xx + inv[1, 1] * yy + inv[1, 2]))
    horizontal = smooth((xx - 150) / 850)
    lower = smooth((yy - 1150) / 220) * np.maximum(0, 1 - np.abs(xx - 570) / 420)
    mx = (maps[0][0] * (1 - horizontal) + maps[1][0] * horizontal) * (1 - lower) + maps[2][0] * lower
    my = (maps[0][1] * (1 - horizontal) + maps[1][1] * horizontal) * (1 - lower) + maps[2][1] * lower
    # Keep the reference's lower crop horizontal without inventing unseen pixels.
    row = 1530 - origin[1]
    my += smooth((yy - 1260) / 270) * (ref.shape[0] - 1 - my[row:row + 1, :])
    aligned = cv2.remap(rgba, mx.astype(np.float32), my.astype(np.float32),
                        cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT)

    # Reveal only near/outside the old crop. Never duplicate the head or eyes.
    inside = np.minimum.reduce([xx, 1144 - xx, 1373 - yy])
    keep = 1 - smooth((inside - 45) / 25)
    aligned[:, :, 3] = (aligned[:, :, 3] * keep).astype(np.uint8)
    # Match the left upper sleeve to the original shoulder. Its old position
    # left a transparent gap beneath the feathered trim. Keep the old crop
    # fade intact; shifting only this added area avoids exposing cut-off cloth.
    shoulder = (smooth((xx - 1030) / 60) * smooth((yy - 760) / 60)
                * (1 - smooth((yy - 920) / 90)))
    aligned = cv2.remap(aligned, (xx - origin[0]).astype(np.float32),
                        (yy - origin[1] + 30 * shoulder).astype(np.float32),
                        cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT)
    path = PROJECT / 'frame_extension.png'
    cv2.imwrite(str(path), aligned)
    print('Wrote', path)


if __name__ == '__main__':
    make_extension()
