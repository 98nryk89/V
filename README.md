# V — Live2D 配信モデル制作

フクロウを連れた黒銀髪キャラを Live2D 化し、配信で動かすための作業リポジトリ。

**使用ソフト:** Live2D Cubism Editor（モデリング）→ VTube Studio（トラッキング）→ OBS（配信）

## 流れ

| 段階 | 作業 | 資料 | テスト |
|---|---|---|---|
| 1 | 素材解析・方針決定 | [docs/01_analysis.md](docs/01_analysis.md) | T0 |
| 2 | 高解像度化・パーツ分け・描き足し | [docs/02_psd_parts.md](docs/02_psd_parts.md) | T1 |
| 3 | Cubism モデリング・物理・書き出し | [docs/03_rigging.md](docs/03_rigging.md) | T2〜T5 |
| 4 | VTube Studio / OBS 設定 | [docs/04_vts_obs.md](docs/04_vts_obs.md) | T6〜T9 |

テストの詳細と記録: [docs/05_test_plan.md](docs/05_test_plan.md)

## 現在の状態

- T0 **不合格**: 元絵は約 1000〜1500px の 1 枚絵。**次は段階 2（高解像度化＋パーツ分け PSD）**

## フォルダ

```
art/reference/   元イラスト（全身 / 拡大）
art/psd/         パーツ分け PSD（段階 2 で追加）
model/runtime/   Cubism 書き出し + VTS 設定（段階 3〜4 で追加）
tools/           検証スクリプト
tests/           検証スクリプト自体のテスト
```

## 検証スクリプト

```sh
pip install -r requirements.txt

python tools/check_source.py art/reference/*.webp     # T0
python tools/check_psd.py art/psd/model.psd           # T1（--strict で推奨パーツも必須扱い）
python tools/check_model.py model/runtime/            # T5

python -m pytest                                      # スクリプト自体のテスト
```

終了コードは、合格なら 0、不合格なら 1 です。
