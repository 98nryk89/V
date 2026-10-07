# V

Claude Code に日本語で指示するだけで、Adobe Firefly で画像を生成する連携です。

## セットアップ

1. [Adobe Developer Console](https://developer.adobe.com/console) でプロジェクトを作成し、
   **Firefly Services API** を追加（認証方式は **OAuth Server-to-Server**）。
   ※ Firefly API の利用には Firefly Services の契約（エンタープライズ/トライアル）が必要です。
2. 発行された Client ID / Client Secret を `.env` に設定:
   ```sh
   cp .env.example .env
   # FIREFLY_CLIENT_ID と FIREFLY_CLIENT_SECRET を記入
   ```
   Claude Code on the web で使う場合は、環境設定の環境変数に同じ 2 つを登録し、
   ネットワークで `ims-na1.adobelogin.com` と `firefly-api.adobe.io`、
   および画像ダウンロード先 (`*.amazonaws.com` 等の署名付き URL) を許可してください。
3. Python 3.8 以上があれば追加インストールは不要です。

## 使い方

### Claude Code から（おすすめ）

```
/firefly 桜並木を歩く柴犬、春の朝の柔らかい光、写真風
```

または普通に「Firefly で〇〇の画像を作って」と頼むだけでも、`CLAUDE.md` の指示に従って
Claude がプロンプトを整え、Firefly で生成し、`output/` に保存して結果を報告します。

### 直接実行

```sh
python3 firefly/firefly_generate.py "夕焼けの富士山、水彩画風" -n 2 --size landscape --content-class art
```

| オプション | 説明 |
|---|---|
| `-n` | 生成枚数 (1–4) |
| `--size` | `square` / `landscape` / `portrait` / `widescreen` または `WIDTHxHEIGHT` |
| `--content-class` | `photo` または `art` |
| `--negative` | 含めたくない要素 |
| `--style` | スタイルプリセット（複数可） |
| `--structure-ref` | 構図・ポーズの参考画像（`--structure-strength` 0–100）|
| `--style-ref` | 画風の参考画像（`--style-strength` 1–100）|
| `--seed` | シード値（再現用） |
| `--model` | モデル指定（例: `image4_standard`） |
| `-o` | 保存先（既定: `output/`） |

生成画像と、使ったプロンプト・シードを記録した JSON が `output/` に保存されます。
