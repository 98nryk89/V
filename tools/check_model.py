"""T5: Cubism から書き出した組み込み用ファイルが VTube Studio に読み込める状態かを判定する。

使い方:
    python tools/check_model.py model/runtime/
(フォルダ内の *.model3.json を自動検出。cdi3.json は書き出し時に「表示補助ファイル」を有効にして出力すること)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Report  # noqa: E402

# VTube Studio の初期トラッキング設定が自動で割り当てる標準パラメータ。
CORE_PARAMS = [
    "ParamAngleX", "ParamAngleY", "ParamAngleZ",
    "ParamEyeLOpen", "ParamEyeROpen", "ParamEyeBallX", "ParamEyeBallY",
    "ParamBrowLY", "ParamBrowRY",
    "ParamMouthOpenY", "ParamMouthForm",
    "ParamBodyAngleX", "ParamBodyAngleY", "ParamBodyAngleZ",
    "ParamBreath",
]
# 表情の細かさに効く標準パラメータ。
QUALITY_PARAMS = [
    "ParamEyeLSmile", "ParamEyeRSmile",
    "ParamBrowLX", "ParamBrowRX", "ParamBrowLAngle", "ParamBrowRAngle",
    "ParamBrowLForm", "ParamBrowRForm",
    "ParamCheek",
    "ParamHairFront", "ParamHairSide", "ParamHairBack",
]
MOC_VERSIONS = {1: "3.0", 2: "3.3", 3: "4.0", 4: "4.2", 5: "5.0"}
MAX_TEXTURE = 8192


def _load(path: Path, rep: Report, label: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        rep.fail(f"{label}: {path.name} が見つからない")
    except json.JSONDecodeError as e:
        rep.fail(f"{label}: {path.name} の JSON が壊れている ({e})")
    return None


def check_model(folder: Path) -> Report:
    rep = Report(f"T5 書き出しチェック: {folder}")
    models = sorted(folder.glob("*.model3.json"))
    if len(models) != 1:
        rep.fail(f"*.model3.json が {len(models)} 個 (1 個であること)")
        return rep
    model = _load(models[0], rep, "model3")
    if model is None:
        return rep
    refs = model.get("FileReferences", {})

    _check_moc(folder / refs.get("Moc", ""), rep)
    _check_textures(folder, refs.get("Textures", []), rep)

    params: set[str] | None = None
    if refs.get("DisplayInfo"):
        cdi = _load(folder / refs["DisplayInfo"], rep, "cdi3")
        if cdi is not None:
            params = {p["Id"] for p in cdi.get("Parameters", [])}
            rep.ok(f"パラメータ {len(params)} 個")
            _check_params(params, rep)
    else:
        rep.warn("cdi3.json (表示補助ファイル) が未参照。パラメータ検証をスキップ")

    if refs.get("Physics"):
        _check_physics(folder / refs["Physics"], params, rep)
    else:
        rep.fail("物理演算ファイル (physics3.json) が無い。髪・ケープ・装飾が揺れない")

    exps = refs.get("Expressions", [])
    if exps:
        for e in exps:
            _check_expression(folder / e["File"], e.get("Name", e["File"]), params, rep)
    else:
        rep.warn("表情ファイル (exp3.json) が無い。VTS のホットキー表情を作る場合は追加")

    groups = {g.get("Name"): g.get("Ids", []) for g in model.get("Groups", [])}
    for g in ("EyeBlink", "LipSync"):
        if groups.get(g):
            rep.ok(f"グループ {g}: {', '.join(groups[g])}")
        else:
            rep.warn(f"グループ {g} が未設定 (Cubism の「まばたき/リップシンクの設定」)")

    if not list(folder.glob("*.vtube.json")):
        rep.warn("*.vtube.json 無し。VTS で初回読み込み後に生成される")
    return rep


def _check_moc(path: Path, rep: Report) -> None:
    if not path.is_file():
        rep.fail(f"moc3 が見つからない: {path.name}")
        return
    head = path.read_bytes()[:5]
    if head[:4] != b"MOC3":
        rep.fail(f"{path.name}: moc3 形式ではない")
        return
    ver = MOC_VERSIONS.get(head[4], f"不明 ({head[4]})")
    rep.ok(f"moc3 形式 Cubism {ver}")


def _check_textures(folder: Path, textures: list[str], rep: Report) -> None:
    if not textures:
        rep.fail("テクスチャが参照されていない")
        return
    for t in textures:
        p = folder / t
        if not p.is_file():
            rep.fail(f"テクスチャが見つからない: {t}")
            continue
        w, h = Image.open(p).size
        pow2 = w == h and (w & (w - 1)) == 0
        if not pow2:
            rep.fail(f"{t}: {w}x{h} (正方形の 2 の累乗であること)")
        elif w > MAX_TEXTURE:
            rep.fail(f"{t}: {w}px は大きすぎる (最大 {MAX_TEXTURE})")
        else:
            rep.ok(f"{t}: {w}x{h}")
    if len(textures) > 4:
        rep.warn(f"テクスチャ {len(textures)} 枚。VRAM 負荷が配信 PC で問題ないか確認")


def _check_params(params: set[str], rep: Report) -> None:
    missing = [p for p in CORE_PARAMS if p not in params]
    if missing:
        rep.fail(f"必須標準パラメータ不足: {', '.join(missing)}")
    else:
        rep.ok("必須標準パラメータ揃っている")
    missing = [p for p in QUALITY_PARAMS if p not in params]
    if missing:
        rep.warn(f"品質用標準パラメータ不足: {', '.join(missing)}")
    else:
        rep.ok("品質用標準パラメータ揃っている")


def _check_physics(path: Path, params: set[str] | None, rep: Report) -> None:
    phys = _load(path, rep, "physics3")
    if phys is None:
        return
    settings = phys.get("PhysicsSettings", [])
    declared = phys.get("Meta", {}).get("PhysicsSettingCount")
    if declared != len(settings):
        rep.fail(f"physics3: Meta の設定数 {declared} と実数 {len(settings)} が不一致")
    rep.ok(f"物理演算グループ {len(settings)} 個")
    inputs: set[str] = set()
    for i, s in enumerate(settings):
        name = s.get("Id", f"#{i}")
        ins = [x["Source"]["Id"] for x in s.get("Input", [])]
        outs = [x["Destination"]["Id"] for x in s.get("Output", [])]
        inputs.update(ins)
        if not ins:
            rep.fail(f"物理 {name}: 入力が無い")
        if not outs:
            rep.fail(f"物理 {name}: 出力が無い")
        if params is not None:
            unknown = [p for p in ins + outs if p not in params]
            if unknown:
                rep.fail(f"物理 {name}: 存在しないパラメータ {', '.join(unknown)}")
    for need in ("ParamAngleX", "ParamAngleZ", "ParamBodyAngleX"):
        if need not in inputs:
            rep.warn(f"どの物理グループも {need} を入力にしていない")


def _check_expression(path: Path, name: str, params: set[str] | None, rep: Report) -> None:
    exp = _load(path, rep, f"表情 {name}")
    if exp is None:
        return
    ids = [p["Id"] for p in exp.get("Parameters", [])]
    if params is not None:
        unknown = [p for p in ids if p not in params]
        if unknown:
            rep.fail(f"表情 {name}: 存在しないパラメータ {', '.join(unknown)}")
            return
    rep.ok(f"表情 {name}: {len(ids)} パラメータ")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("folder", type=Path)
    args = ap.parse_args(argv)
    rep = check_model(args.folder)
    print(rep.render())
    return 0 if rep.passed else 1


if __name__ == "__main__":
    sys.exit(main())
