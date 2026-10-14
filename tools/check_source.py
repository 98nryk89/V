"""T0: 元イラストが Live2D 素材として使える状態かを判定する。

使い方:
    python tools/check_source.py art/reference/fullbody.webp art/reference/bustup.webp
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Report  # noqa: E402

# 配信用バストアップ〜全身モデルで一般的に求められる最低ライン。
MIN_LONG_SIDE = 4000
# これ未満だと拡大時に線がぼけ、テクスチャ密度が足りない。
HARD_MIN_LONG_SIDE = 2500


def check_image(path: Path, min_long_side: int = MIN_LONG_SIDE) -> Report:
    rep = Report(f"T0 素材チェック: {path.name}")
    if path.suffix.lower() == ".psd":
        from psd_tools import PSDImage

        psd = PSDImage.open(path)
        w, h = psd.size
        layers = [l for l in psd.descendants() if not l.is_group()]
        _check_size(rep, w, h, min_long_side)
        if len(layers) < 2:
            rep.fail(f"PSDだがレイヤーが {len(layers)} 枚しかない (パーツ分け未実施)")
        else:
            rep.ok(f"PSD レイヤー数 {len(layers)}")
        return rep

    im = Image.open(path)
    w, h = im.size
    _check_size(rep, w, h, min_long_side)
    if "A" in im.getbands():
        rep.ok("アルファチャンネルあり")
    else:
        rep.warn(f"アルファなし ({im.mode})。背景の切り抜きが必要")
    rep.fail("1枚絵 (レイヤー無し)。Live2D に読み込むにはパーツ分けした PSD が必要")
    if path.suffix.lower() in {".webp", ".jpg", ".jpeg"}:
        rep.warn(f"{path.suffix} は非可逆圧縮。線周りの圧縮ノイズを清書時に除去すること")
    return rep


def _check_size(rep: Report, w: int, h: int, min_long_side: int) -> None:
    long_side = max(w, h)
    if long_side >= min_long_side:
        rep.ok(f"解像度 {w}x{h}")
    elif long_side >= HARD_MIN_LONG_SIDE:
        rep.warn(f"解像度 {w}x{h}: 長辺 {min_long_side}px 以上を推奨")
    else:
        need = min_long_side / long_side
        rep.fail(f"解像度 {w}x{h}: 長辺 {min_long_side}px に対し約 {need:.1f} 倍不足")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--min-long-side", type=int, default=MIN_LONG_SIDE)
    args = ap.parse_args(argv)
    ok = True
    for f in args.files:
        rep = check_image(f, args.min_long_side)
        print(rep.render(), end="\n\n")
        ok &= rep.passed
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
