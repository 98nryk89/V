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
| 3' | 上半身を先に完成 → 後から全身へ拡張（※外注前提の部分は 07 に置き換え） | [docs/06_upper_body_plan.md](docs/06_upper_body_plan.md) | |
| **★** | **AI だけで完結させる計画（現在の計画。iki + MediaPipe + OBS）** | [docs/07_ai_only_plan.md](docs/07_ai_only_plan.md) | P0〜P6 |
| 4 | VTube Studio / OBS 設定 | [docs/04_vts_obs.md](docs/04_vts_obs.md) | T6〜T9 |

テストの詳細と記録: [docs/05_test_plan.md](docs/05_test_plan.md)

## 現在の状態

- **方針: 外注・手作業なし。AI の指示だけで完結させる**（[docs/07_ai_only_plan.md](docs/07_ai_only_plan.md)）
- P0 済: 上半身の絵を 4 倍に拡大・透過済み `art/work/upper_x4_rgba.png`（4576×5500）
- P1 パーツ分け・自動リグ: 第 1 版 済 `model/iki/upper_s.iki`
- P3 トラッキング + OBS 用ページ: 第 1 版 済（`app/`、使い方は [docs/08_usage.md](docs/08_usage.md)）。**実機での確認待ち**

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
