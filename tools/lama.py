"""LaMa (big-lama, TorchScript) によるインペイント。CPU でも動く。

重み: https://github.com/Sanster/models/releases/download/add_big_lama/big-lama.pt  (Apache-2.0)
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import torch

_model = None


def _load(weights: Path):
    global _model
    if _model is None:
        _model = torch.jit.load(str(weights), map_location="cpu").eval()
    return _model


def default_weights() -> Path:
    p = os.environ.get("LAMA_WEIGHTS")
    if not p:
        raise RuntimeError("環境変数 LAMA_WEIGHTS に big-lama.pt のパスを指定してください")
    return Path(p)


@torch.inference_mode()
def inpaint(rgb: np.ndarray, mask: np.ndarray, weights: Path | None = None) -> np.ndarray:
    """rgb: HxWx3 uint8、mask: HxW bool（True = 塗り直す）。戻り値は HxWx3 uint8。"""
    model = _load(weights or default_weights())
    h, w = mask.shape
    ph, pw = (-h) % 8, (-w) % 8
    x = torch.from_numpy(rgb.astype(np.float32) / 255.0).permute(2, 0, 1)[None]
    m = torch.from_numpy(mask.astype(np.float32))[None, None]
    x = torch.nn.functional.pad(x, (0, pw, 0, ph), mode="reflect")
    m = torch.nn.functional.pad(m, (0, pw, 0, ph), mode="constant")
    out = model(x, (m > 0.5).float())[0].permute(1, 2, 0).clamp(0, 1).numpy()[:h, :w]
    res = (out * 255.0 + 0.5).astype(np.uint8)
    keep = ~mask[..., None]
    return np.where(keep, rgb, res)
