"""T1: パーツ分け PSD が Cubism Editor に読み込める状態かを判定する。

使い方:
    python tools/check_psd.py art/psd/model.psd
    python tools/check_psd.py art/psd/model.psd --strict   # 推奨パーツ不足も FAIL 扱い
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Report  # noqa: E402

MANIFEST = Path(__file__).resolve().parent / "parts_manifest.json"
MIN_LONG_SIDE = 4000
# Cubism へ取り込む前にラスタライズ/統合が必要なレイヤー種別。
RASTERIZE_KINDS = {"type", "shape", "smartobject", "adjustment", "fill"}
SAFE_BLEND = {"NORMAL", "PASS_THROUGH"}


@dataclass
class LayerInfo:
    name: str
    path: str
    kind: str
    blend: str = "NORMAL"
    clipping: bool = False
    mask: bool = False
    effects: bool = False
    empty: bool = False
    visible: bool = True


def collect_layers(psd) -> list[LayerInfo]:
    out: list[LayerInfo] = []

    def walk(group, prefix: str) -> None:
        for layer in group:
            path = f"{prefix}/{layer.name}"
            empty = False
            if layer.kind == "pixel":
                im = layer.topil()
                empty = im is None or ("A" in im.getbands() and im.getchannel("A").getextrema()[1] == 0)
            mask = layer.mask is not None and not layer.mask.disabled and layer.kind != "group"
            out.append(
                LayerInfo(
                    name=layer.name,
                    path=path,
                    kind=layer.kind,
                    blend=layer.blend_mode.name,
                    clipping=bool(layer.clipping),
                    mask=mask,
                    effects=layer.has_effects(),
                    empty=empty,
                    visible=layer.visible,
                )
            )
            if layer.is_group():
                walk(layer, path)

    walk(psd, "")
    return out


def check_layers(layers: list[LayerInfo], manifest: dict, strict: bool, rep: Report) -> None:
    drawables = [l for l in layers if l.kind != "group"]
    rep.ok(f"レイヤー {len(drawables)} 枚 / グループ {len(layers) - len(drawables)} 個")

    for l in layers:
        if l.kind in RASTERIZE_KINDS:
            rep.fail(f"{l.path}: {l.kind} レイヤー。ラスタライズすること")
        if l.effects:
            rep.fail(f"{l.path}: レイヤー効果は Cubism で無視される。ラスタライズすること")
        if l.mask:
            rep.warn(f"{l.path}: レイヤーマスクあり。適用してから取り込むこと")
        if l.clipping:
            rep.warn(f"{l.path}: クリッピング。下のレイヤーへ統合するか Cubism 側で再設定すること")
        if l.kind != "group" and l.blend not in SAFE_BLEND:
            rep.warn(f"{l.path}: 描画モード {l.blend}。Cubism 上の見た目を要確認")
        if l.empty:
            rep.warn(f"{l.path}: 空レイヤー")
        if not l.visible:
            rep.warn(f"{l.path}: 非表示レイヤー (取り込み時の扱いを確認)")

    dup = [n for n, c in Counter(l.name for l in drawables).items() if c > 1]
    for n in dup:
        rep.warn(f"レイヤー名重複: {n}  (パーツ/デフォーマ ID が判別しにくくなる)")

    names = [l.name.lower() for l in drawables]
    for level, groups in (("required", manifest["required"]), ("recommended", manifest["recommended"])):
        for category, patterns in groups.items():
            missing = [p for p in patterns if not any(fnmatch.fnmatch(n, p.lower()) for n in names)]
            if not missing:
                rep.ok(f"{category}: 揃っている")
            elif level == "required" or strict:
                rep.fail(f"{category}: 不足 {', '.join(missing)}")
            else:
                rep.warn(f"{category}: 不足 {', '.join(missing)}")


def check_psd(path: Path, strict: bool = False, min_long_side: int = MIN_LONG_SIDE) -> Report:
    from psd_tools import PSDImage

    rep = Report(f"T1 PSD チェック: {path.name}")
    psd = PSDImage.open(path)
    w, h = psd.size
    if max(w, h) >= min_long_side:
        rep.ok(f"キャンバス {w}x{h}")
    else:
        rep.fail(f"キャンバス {w}x{h}: 長辺 {min_long_side}px 以上にすること")
    if psd.color_mode.name != "RGB":
        rep.fail(f"カラーモード {psd.color_mode.name}: RGB にすること")
    if psd.depth != 8:
        rep.fail(f"{psd.depth}bit: 8bit/チャンネルにすること")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    check_layers(collect_layers(psd), manifest, strict, rep)
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("psd", type=Path)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--min-long-side", type=int, default=MIN_LONG_SIDE)
    args = ap.parse_args(argv)
    rep = check_psd(args.psd, args.strict, args.min_long_side)
    print(rep.render())
    return 0 if rep.passed else 1


if __name__ == "__main__":
    sys.exit(main())
