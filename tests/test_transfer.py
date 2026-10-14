import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import transfer_highres as th  # noqa: E402


def _make_inputs(tmp_path: Path):
    """低解像度 (40x60) の 2 レイヤー PSD と、x4 の高解像度元絵を作る。

    back: 全面の青い四角（前のレイヤーに隠れる部分は描き足し済み = 青）
    front: 中央の赤い四角
    高解像度の元絵は、見えている部分にだけ細かい縞模様がある。
    """
    from psd_tools import PSDImage
    from psd_tools.api.layers import Group, PixelLayer

    lw, lh, s = 40, 60, 4
    back = np.zeros((lh, lw, 4), np.uint8)
    back[5:55, 5:35] = (0, 0, 255, 255)
    front = np.zeros((lh, lw, 4), np.uint8)
    front[20:40, 10:30] = (255, 0, 0, 255)
    psd = PSDImage.new("RGBA", (lw, lh))
    g = Group.new(psd, "body")
    PixelLayer.frompil(Image.fromarray(back), g, "back")
    PixelLayer.frompil(Image.fromarray(front), g, "front")
    psd_path = tmp_path / "lo.psd"
    psd.save(psd_path)

    hi = np.zeros((lh * s, lw * s, 4), np.uint8)
    hi[5 * s : 55 * s, 5 * s : 35 * s] = (0, 0, 255, 255)
    hi[20 * s : 40 * s, 10 * s : 30 * s] = (255, 0, 0, 255)
    hi[::2, :, 1] = np.where(hi[::2, :, 3] > 0, 60, 0)  # 高解像度だけにある細部
    hi_path = tmp_path / "hi.png"
    Image.fromarray(hi).save(hi_path)
    return psd_path, hi_path, hi


def test_transfer_keeps_hires_detail_and_inpainted_hidden_area(tmp_path):
    from psd_tools import PSDImage

    psd_path, hi_path, hi = _make_inputs(tmp_path)
    dst = tmp_path / "out.psd"
    assert th.main([str(psd_path), str(hi_path), str(dst)]) == 0

    out = PSDImage.open(dst)
    assert out.size == (160, 240)
    assert [l.name for l in out.descendants()] == ["body", "back", "front"]
    back, front = out[0][0], out[0][1]

    def px(layer, x, y):
        l, t, _, _ = layer.bbox
        return np.asarray(layer.topil().convert("RGBA"))[y - t, x - l]

    # 見えている部分は高解像度の元絵（縞の G=60 が残る）
    assert tuple(px(front, 80, 120)) == (255, 60, 0, 255)
    assert tuple(px(back, 40, 40)) == (0, 60, 255, 255)
    # back の隠れていた部分は描き足し（拡大した青）
    assert tuple(px(back, 80, 120)) == (0, 0, 255, 255)


def test_recompose_matches_source(tmp_path):
    from psd_tools import PSDImage

    psd_path, _, hi = _make_inputs(tmp_path)
    leaves = th._leaf_layers(PSDImage.open(psd_path))
    hif = hi.astype(np.float32) / 255
    layers = th.transfer(leaves, hif)
    comp = th.recompose(layers, (160, 240), [True, True])
    mask = hif[..., 3] > 0.5
    err = np.abs(comp[..., :3] - hif[..., :3])[mask].mean() * 255
    assert err < 3, err


def test_aspect_mismatch_rejected(tmp_path):
    from psd_tools import PSDImage
    import pytest

    psd_path, _, _ = _make_inputs(tmp_path)
    leaves = th._leaf_layers(PSDImage.open(psd_path))
    with pytest.raises(ValueError):
        th.transfer(leaves, np.zeros((100, 100, 4), np.float32))
