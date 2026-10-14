# V — 全身 Live2D 配信モデル制作

フクロウを連れた黒銀髪キャラの生成イラストを、大手事務所水準の全身 Live2D モデルにして配信で動かすための作業リポジトリ。

**ツール構成:** AI で素材作り（拡大・透過・See-through によるレイヤー分解）→ Live2D Cubism でリギング（外注可）→ VTube Studio（iPhone トラッキング）→ OBS
選定理由: [docs/00_toolchain.md](docs/00_toolchain.md)

## 流れ

| 段階 | 作業 | 資料 | テスト |
|---|---|---|---|
| 0 | ツール選定 | [docs/00_toolchain.md](docs/00_toolchain.md) | — |
| 1 | 素材解析 | [docs/01_analysis.md](docs/01_analysis.md) | T0 |
| 2 | 拡大・透過・AI レイヤー分解・仕上げ（A1〜A5） | [docs/02_psd_parts.md](docs/02_psd_parts.md) | T0, TA4, T1 |
| 3 | Cubism リギング・物理・書き出し | [docs/03_rigging.md](docs/03_rigging.md) | T2〜T5 |
| 4 | VTube Studio / OBS 設定 | [docs/04_vts_obs.md](docs/04_vts_obs.md) | T6〜T9 |

テストの詳細と記録: [docs/05_test_plan.md](docs/05_test_plan.md)

## 現在の状態

- A1 拡大、A2 透過、A2.5 顔・フクロウの上書きは**済**: `art/work/fullbody_x4_patched.png`（4096×6144）
- T0 は解像度と透過が合格。残りはパーツ分け
- **次: A3 See-through によるレイヤー分解（GPU が必要）** → 出力 PSD を `art/psd/seethrough_raw.psd` に置く

## フォルダ

```
art/reference/   元イラスト（全身 / 拡大）
art/work/        拡大・透過済み素材
art/psd/         パーツ分け PSD
model/runtime/   Cubism 書き出し + VTS 設定
tools/           作業・検証スクリプト
tests/           スクリプトのテスト
```

## スクリプト

```sh
pip install -r requirements.txt

# 素材作り
python tools/upscale.py art/reference/fullbody.webp art/work/fullbody_x4.png --weights RealESRGAN_x4plus_anime_6B.pth
python tools/remove_bg.py art/work/fullbody_x4.png art/work/fullbody_x4_rgba.png --model isnet-anime.onnx --mask-src art/reference/fullbody.webp
python tools/patch_detail.py art/work/fullbody_x4_rgba.png art/work/bustup_x4_rgba.png art/work/fullbody_x4_patched.png
python tools/transfer_highres.py art/psd/seethrough_raw.psd art/work/fullbody_x4_patched.png art/psd/model_draft.psd

# 検証
python tools/check_source.py art/work/fullbody_x4_rgba.png   # T0
python tools/check_psd.py art/psd/model.psd                  # T1（--strict で推奨パーツも必須）
python tools/check_model.py model/runtime/                   # T5

python -m pytest
```

AI モデルの重み（リポジトリには含めない）:
- Real-ESRGAN anime 6B: https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth
- ISNet-anime: https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-anime.onnx
