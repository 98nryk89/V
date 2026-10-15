"""Background removal for illustrations with a baked-in checkerboard 'transparency' background.

The fake-transparent background is (almost) perfectly neutral gray (saturation <= ~5),
whereas the character's hair/skin/clothes are tinted. We:
  1. take neutral mid-gray pixels connected to the image border,
  2. add enclosed pockets (hair gaps etc.) whose statistics look like a two-tone checker
     (mean ~180, high std) - this separates them from white shirt / white feathers,
  3. refine the boundary: re-estimate alpha for the antialiased rim and
     de-contaminate the rim colour so no gray halo is left.
"""
import numpy as np
import cv2
from scipy import ndimage as ndi


def _neutral_candidates(rgb, sat_max=5, lo=110, hi=240):
    sat = rgb.max(2) - rgb.min(2)
    val = rgb.mean(2)
    return (sat <= sat_max) & (val > lo) & (val < hi), sat, val


def remove_checker_background(bgr, extra_bg_seeds=(), debug=False):
    """Return float alpha (H,W) in [0,1] and decontaminated BGR uint8 image."""
    rgb = bgr[..., ::-1].astype(np.int32)
    cand, sat, val = _neutral_candidates(rgb)
    h, w = cand.shape

    lab, _ = ndi.label(cand)
    border = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    sizes_l = ndi.sum(cand, lab, range(1, lab.max() + 1))
    bg = np.zeros_like(cand)
    for L in border[border != 0]:
        m = lab == L
        # big components are the backdrop; small ones touching the frame (e.g. silver trim on a
        # cropped sleeve) must still look like a two-tone checker to be removed
        if sizes_l[L - 1] >= 5000:
            bg |= m
        else:
            v = val[m]
            if 165 <= v.mean() <= 195 and 14 <= v.std() <= 60:
                bg |= m

    # enclosed pockets that look like checker (mean ~180, std high); white clothes are ~231, std<10
    rest = (cand & ~bg).astype(np.uint8)
    rest = cv2.morphologyEx(rest, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    lab2, n2 = ndi.label(rest)
    for i, sl in enumerate(ndi.find_objects(lab2), 1):
        m = lab2[sl] == i
        a = int(m.sum())
        if a < 40:
            continue
        v = val[sl][m]
        mid = ((v > 165) & (v < 190)).mean()
        bimodal = ((v < 160) | (v > 195)).mean()
        is_checker = 165 <= v.mean() <= 195 and 14 <= v.std() <= 60 and (
            a >= 200 or (mid <= 0.3 and bimodal >= 0.55))
        if is_checker:
            full = np.zeros_like(bg)
            full[sl] = m
            bg |= full

    # user/AI supplied seeds ("this point is background")
    for (x, y) in extra_bg_seeds:
        if cand[y, x]:
            bg |= (lab == lab[y, x])

    # tidy: drop tiny specks of 'foreground' inside bg and tiny bg specks inside fg
    # gray fringe: low-saturation pixels hugging the background are antialiasing mixed with checker
    near_bg = ndi.binary_dilation(bg, iterations=2)
    fringe = near_bg & (sat <= 7) & (val > 100) & (val < 238)
    bg = bg | fringe
    fg = ndi.binary_opening(~bg, structure=np.ones((2, 2)))
    fg = ndi.binary_opening(fg, structure=np.ones((2, 2)))
    lab_f, nf = ndi.label(fg)
    sizes = ndi.sum(fg, lab_f, range(1, nf + 1))
    fg = np.isin(lab_f, 1 + np.flatnonzero(sizes >= 150))

    # --- rim refinement -------------------------------------------------------
    # Antialiased rim = alpha*F + (1-alpha)*B, B = neutral checker tone (estimated from the
    # nearest clean background pixel), F = nearest solid foreground colour. For dark F
    # (black hair strands) we can solve alpha from luminance; for light F we keep a hard edge.
    gray = bgr.astype(np.float32).mean(2)
    solid = ndi.binary_erosion(fg, iterations=3)
    clean_bg = ~ndi.binary_dilation(fg, iterations=5)
    _, fi = ndi.distance_transform_edt(~solid, return_indices=True)
    _, bi = ndi.distance_transform_edt(~clean_bg, return_indices=True)
    F = bgr[fi[0], fi[1]].astype(np.float32)
    Fg = F.mean(2)
    Bg = gray[bi[0], bi[1]]
    band = ndi.binary_dilation(fg, iterations=3) & ~solid
    dark = Fg < 110
    a_lum = np.clip((Bg - gray) / np.maximum(Bg - Fg, 20.0), 0, 1)
    a_lum[a_lum < 0.18] = 0
    alpha = np.where(solid, 1.0, 0.0).astype(np.float32)
    alpha = np.where(band & dark, a_lum, alpha)
    alpha = np.where(band & ~dark, np.where(ndi.binary_erosion(fg, iterations=1), 1.0, 0.0), alpha)
    # soften hard (light-F) edges slightly
    alpha = np.where(band & ~dark, cv2.GaussianBlur(alpha, (0, 0), 0.7), alpha)
    # keep only pixels connected to the main figure's neighbourhood (drop isolated specks)
    keep = ndi.binary_dilation(fg, iterations=3)
    alpha[~keep] = 0
    out_col = np.where((band & (alpha < 1))[..., None], F, bgr.astype(np.float32))
    out = np.where(alpha[..., None] > 0, out_col, 0).astype(np.uint8)
    return alpha, out
