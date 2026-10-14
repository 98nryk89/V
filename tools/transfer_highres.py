"""A4: AI 分解 PSD（低解像度）を、高解像度の元絵を使って高解像度 PSD に作り直す。

See-through などの自動レイヤー分解は 1024〜1280px 程度で処理されるため、そのままでは解像度が足りない。
このスクリプトでは、各レイヤーのうち元絵で「見えている」部分を高解像度の元絵の画素に置き換える。
描き足された「隠れている」部分は、レイヤー自体を拡大したものを使う。

使い方:
    python tools/transfer_highres.py decomposed.psd art/work/fullbody_x4_rgba.png art/psd/model_draft.psd

前提: 分解 PSD と高解像度画像は同じ構図（縦横比が同じ、余白なし）であること。
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

OWN_ALPHA = 0.5  # このアルファ以上で一番手前のレイヤーを、その画素の「持ち主」とする


@dataclass
class Leaf:
    layer: object  # psd_tools Layer
    rgba: np.ndarray  # キャンバスサイズ float32 0..1
    visible: bool


def _leaf_layers(psd) -> list[Leaf]:
    leaves = []
    w, h = psd.size
    for layer in psd.descendants():  # 下から上の順
        if layer.is_group() or layer.kind != "pixel":
            continue
        canvas = np.zeros((h, w, 4), dtype=np.float32)
        im = layer.topil()
        if im is not None:
            im = im.convert("RGBA")
            l, t, r, b = layer.bbox
            arr = np.asarray(im, dtype=np.float32) / 255.0
            # キャンバス外にはみ出した部分を切り落とす
            sl, st = max(-l, 0), max(-t, 0)
            l2, t2, r2, b2 = max(l, 0), max(t, 0), min(r, w), min(b, h)
            if r2 > l2 and b2 > t2:
                canvas[t2:b2, l2:r2] = arr[st : st + b2 - t2, sl : sl + r2 - l2]
            canvas[..., 3] *= layer.opacity / 255.0
        leaves.append(Leaf(layer, canvas, _effectively_visible(layer)))
    return leaves


def _effectively_visible(layer) -> bool:
    node = layer
    while node is not None and hasattr(node, "visible"):
        if not node.visible:
            return False
        node = node.parent
    return True


def owner_map(leaves: list[Leaf]) -> np.ndarray:
    h, w = leaves[0].rgba.shape[:2]
    owner = np.full((h, w), -1, dtype=np.int32)
    for i, leaf in enumerate(leaves):
        if leaf.visible:
            owner[leaf.rgba[..., 3] >= OWN_ALPHA] = i
    return owner


def _resize(arr: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """float 0..1 の HxW または HxWxC を (w, h) へ拡大。"""
    if arr.ndim == 2:
        return np.asarray(Image.fromarray(arr.astype(np.float32), "F").resize(size, Image.BILINEAR))
    return np.stack([_resize(arr[..., c], size) for c in range(arr.shape[2])], axis=-1)


def _upscale_layer(rgba: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    # 乗算済みアルファで拡大して、縁のにじみ（黒/白フチ）を防ぐ
    a = rgba[..., 3:4]
    pre = np.concatenate([rgba[..., :3] * a, a], axis=-1)
    up = np.clip(_resize(pre, size), 0, 1)
    ua = up[..., 3:4]
    rgb = np.where(ua > 1e-4, up[..., :3] / np.maximum(ua, 1e-4), 0)
    return np.concatenate([np.clip(rgb, 0, 1), ua], axis=-1)


def transfer(leaves: list[Leaf], hi: np.ndarray, pad: int = 4) -> list[tuple[np.ndarray, tuple[int, int]]]:
    """各レイヤーを高解像度化。戻り値: (bbox 内 RGBA uint8, (left, top))"""
    lh, lw = leaves[0].rgba.shape[:2]
    hh, hw = hi.shape[:2]
    if abs(lw / lh - hw / hh) > 0.01:
        raise ValueError(f"縦横比が違う: 分解 PSD {lw}x{lh} / 高解像度 {hw}x{hh}")
    sx, sy = hw / lw, hh / lh
    owner = owner_map(leaves)
    out = []
    for i, leaf in enumerate(leaves):
        ys, xs = np.nonzero(leaf.rgba[..., 3] > 0)
        if len(xs) == 0:
            out.append((np.zeros((1, 1, 4), np.uint8), (0, 0)))
            continue
        l0, t0 = max(xs.min() - pad, 0), max(ys.min() - pad, 0)
        r0, b0 = min(xs.max() + 1 + pad, lw), min(ys.max() + 1 + pad, lh)
        L, T = int(round(l0 * sx)), int(round(t0 * sy))
        R, B = int(round(r0 * sx)), int(round(b0 * sy))
        size = (R - L, B - T)

        up = _upscale_layer(leaf.rgba[t0:b0, l0:r0], size)
        vis = _resize((owner[t0:b0, l0:r0] == i).astype(np.float32), size)[..., None]
        src = hi[T:B, L:R]
        rgb = vis * src[..., :3] + (1 - vis) * up[..., :3]
        alpha = vis[..., 0] * src[..., 3] + (1 - vis[..., 0]) * up[..., 3]
        res = np.concatenate([rgb, alpha[..., None]], axis=-1)
        out.append(((res * 255 + 0.5).astype(np.uint8), (L, T)))
    return out


def write_psd(src_psd, leaves: list[Leaf], layers_hi, size: tuple[int, int], dst: Path) -> None:
    from psd_tools import PSDImage
    from psd_tools.api.layers import Group, PixelLayer

    out = PSDImage.new("RGBA", size)
    groups = {id(src_psd): out}
    hi_by_layer = {id(leaf.layer): hi for leaf, hi in zip(leaves, layers_hi)}

    def walk(src_group) -> None:
        dst_group = groups[id(src_group)]
        for layer in src_group:
            if layer.is_group():
                g = Group.new(dst_group, layer.name)
                g.visible = layer.visible
                groups[id(layer)] = g
                walk(layer)
            elif id(layer) in hi_by_layer:
                arr, (left, top) = hi_by_layer[id(layer)]
                new = PixelLayer.frompil(Image.fromarray(arr, "RGBA"), dst_group, layer.name, top, left)
                new.visible = layer.visible
                new.blend_mode = layer.blend_mode

    walk(src_psd)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst)


def recompose(layers_hi, size: tuple[int, int], visible: list[bool]) -> np.ndarray:
    w, h = size
    canvas = np.zeros((h, w, 4), dtype=np.float32)
    for (arr, (left, top)), vis in zip(layers_hi, visible):
        if not vis:
            continue
        a = arr.astype(np.float32) / 255.0
        ah, aw = a.shape[:2]
        reg = canvas[top : top + ah, left : left + aw]
        a = a[: reg.shape[0], : reg.shape[1]]
        sa = a[..., 3:4]
        out_a = sa + reg[..., 3:4] * (1 - sa)
        rgb = (a[..., :3] * sa + reg[..., :3] * reg[..., 3:4] * (1 - sa)) / np.maximum(out_a, 1e-6)
        canvas[top : top + ah, left : left + aw] = np.concatenate([rgb, out_a], axis=-1)
    return canvas


def main(argv: list[str] | None = None) -> int:
    from psd_tools import PSDImage

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("decomposed", type=Path)
    ap.add_argument("hires", type=Path)
    ap.add_argument("dst", type=Path)
    args = ap.parse_args(argv)

    psd = PSDImage.open(args.decomposed)
    leaves = _leaf_layers(psd)
    hi_img = Image.open(args.hires).convert("RGBA")
    hi = np.asarray(hi_img, dtype=np.float32) / 255.0
    layers_hi = transfer(leaves, hi)
    write_psd(psd, leaves, layers_hi, hi_img.size, args.dst)

    # 検証: 再合成した画像と高解像度の元絵の差（見えている部分）
    comp = recompose(layers_hi, hi_img.size, [l.visible for l in leaves])
    mask = hi[..., 3] > 0.5
    err = np.abs(comp[..., :3] - hi[..., :3])[mask].mean() * 255 if mask.any() else 0.0
    print(f"{args.dst}: {hi_img.size[0]}x{hi_img.size[1]}, レイヤー {len(leaves)} 枚, 再合成誤差 {err:.2f}/255")
    return 0


if __name__ == "__main__":
    sys.exit(main())
