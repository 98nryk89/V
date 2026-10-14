import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import check_model  # noqa: E402
import check_psd  # noqa: E402
import check_source  # noqa: E402
from check_psd import LayerInfo  # noqa: E402
from common import FAIL, WARN, Report  # noqa: E402

MANIFEST = json.loads((ROOT / "tools" / "parts_manifest.json").read_text(encoding="utf-8"))


def _msgs(rep: Report, level: str) -> list[str]:
    return [m for lv, m in rep.items if lv == level]


# --- T0 ---------------------------------------------------------------


def test_reference_images_are_not_live2d_ready():
    for name in ("fullbody.webp", "bustup.webp"):
        rep = check_source.check_image(ROOT / "art" / "reference" / name)
        assert not rep.passed
        assert any("解像度" in m for m in _msgs(rep, FAIL))
        assert any("1枚絵" in m for m in _msgs(rep, FAIL))


def test_large_image_passes_size(tmp_path):
    p = tmp_path / "big.png"
    Image.new("RGBA", (4000, 6000)).save(p)
    rep = check_source.check_image(p)
    assert not any("解像度" in m for m in _msgs(rep, FAIL))


# --- T1 ---------------------------------------------------------------


def _all_parts() -> list[LayerInfo]:
    names = []
    for groups in (MANIFEST["required"], MANIFEST["recommended"]):
        for pats in groups.values():
            names += [p.replace("*", "1") for p in pats]
    return [LayerInfo(name=n, path=f"/{n}", kind="pixel") for n in names]


def test_complete_layers_pass_strict():
    rep = Report("t")
    check_psd.check_layers(_all_parts(), MANIFEST, strict=True, rep=rep)
    assert rep.passed, rep.render()
    assert not _msgs(rep, WARN)


def test_missing_required_part_fails():
    layers = [l for l in _all_parts() if l.name != "mouth_inner"]
    rep = Report("t")
    check_psd.check_layers(layers, MANIFEST, strict=False, rep=rep)
    assert any("mouth_inner" in m for m in _msgs(rep, FAIL))


def test_missing_recommended_part_only_warns_unless_strict():
    layers = [l for l in _all_parts() if not l.name.startswith("owl_")]
    rep = Report("t")
    check_psd.check_layers(layers, MANIFEST, strict=False, rep=rep)
    assert rep.passed
    assert any("フクロウ" in m for m in _msgs(rep, WARN))
    rep = Report("t")
    check_psd.check_layers(layers, MANIFEST, strict=True, rep=rep)
    assert not rep.passed


def test_problem_layers_are_flagged():
    layers = _all_parts() + [
        LayerInfo("title", "/title", "type"),
        LayerInfo("glow", "/glow", "pixel", effects=True),
        LayerInfo("shade", "/shade", "pixel", clipping=True, blend="MULTIPLY"),
        LayerInfo("face", "/x/face", "pixel"),
    ]
    rep = Report("t")
    check_psd.check_layers(layers, MANIFEST, strict=False, rep=rep)
    fails, warns = " ".join(_msgs(rep, FAIL)), " ".join(_msgs(rep, WARN))
    assert "/title" in fails and "/glow" in fails
    assert "クリッピング" in warns and "MULTIPLY" in warns and "重複: face" in warns


def test_real_psd_file_low_resolution(tmp_path):
    from psd_tools import PSDImage
    from psd_tools.api.layers import PixelLayer

    psd = PSDImage.new("RGB", (400, 600))
    PixelLayer.frompil(Image.new("RGBA", (10, 10), (255, 0, 0, 255)), psd, "face")
    p = tmp_path / "m.psd"
    psd.save(p)
    rep = check_psd.check_psd(p)
    assert any("キャンバス" in m for m in _msgs(rep, FAIL))
    assert any("目: 不足" in m for m in _msgs(rep, FAIL))


# --- T5 ---------------------------------------------------------------


def _runtime(tmp_path: Path, params: list[str], physics_out: str = "ParamHairFront") -> Path:
    (tmp_path / "m.moc3").write_bytes(b"MOC3\x05" + b"\0" * 60)
    tex = tmp_path / "m.4096"
    tex.mkdir()
    Image.new("RGBA", (64, 64)).save(tex / "texture_00.png")
    (tmp_path / "m.cdi3.json").write_text(
        json.dumps({"Version": 3, "Parameters": [{"Id": p, "GroupId": "", "Name": p} for p in params]})
    )
    (tmp_path / "m.physics3.json").write_text(
        json.dumps(
            {
                "Version": 3,
                "Meta": {"PhysicsSettingCount": 1},
                "PhysicsSettings": [
                    {
                        "Id": "PhysicsSetting1",
                        "Input": [
                            {"Source": {"Id": s}} for s in ("ParamAngleX", "ParamAngleZ", "ParamBodyAngleX")
                        ],
                        "Output": [{"Destination": {"Id": physics_out}}],
                    }
                ],
            }
        )
    )
    (tmp_path / "smile.exp3.json").write_text(
        json.dumps({"Type": "Live2D Expression", "Parameters": [{"Id": "ParamEyeLSmile", "Value": 1}]})
    )
    (tmp_path / "m.model3.json").write_text(
        json.dumps(
            {
                "Version": 3,
                "FileReferences": {
                    "Moc": "m.moc3",
                    "Textures": ["m.4096/texture_00.png"],
                    "Physics": "m.physics3.json",
                    "DisplayInfo": "m.cdi3.json",
                    "Expressions": [{"Name": "smile", "File": "smile.exp3.json"}],
                },
                "Groups": [
                    {"Target": "Parameter", "Name": "EyeBlink", "Ids": ["ParamEyeLOpen", "ParamEyeROpen"]},
                    {"Target": "Parameter", "Name": "LipSync", "Ids": ["ParamMouthOpenY"]},
                ],
            }
        )
    )
    (tmp_path / "m.vtube.json").write_text("{}")
    return tmp_path


def test_complete_runtime_passes(tmp_path):
    folder = _runtime(tmp_path, check_model.CORE_PARAMS + check_model.QUALITY_PARAMS)
    rep = check_model.check_model(folder)
    assert rep.passed, rep.render()
    assert not _msgs(rep, WARN), rep.render()
    assert any("Cubism 5.0" in m for lv, m in rep.items)


def test_runtime_missing_core_param_and_bad_physics(tmp_path):
    params = [p for p in check_model.CORE_PARAMS if p != "ParamMouthForm"]
    folder = _runtime(tmp_path, params + ["ParamEyeLSmile"], physics_out="ParamCapeSway")
    rep = check_model.check_model(folder)
    fails = " ".join(_msgs(rep, FAIL))
    assert "ParamMouthForm" in fails
    assert "ParamCapeSway" in fails


def test_runtime_bad_texture(tmp_path):
    folder = _runtime(tmp_path, check_model.CORE_PARAMS)
    Image.new("RGBA", (100, 64)).save(folder / "m.4096" / "texture_00.png")
    rep = check_model.check_model(folder)
    assert any("2 の累乗" in m for m in _msgs(rep, FAIL))
