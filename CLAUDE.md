# V

## 画像生成 (Adobe Firefly)

ユーザーが画像の生成を依頼したら、Adobe Firefly を使う:

```
python3 firefly/firefly_generate.py "<プロンプト>" [-n 1-4] [--size square|landscape|portrait|widescreen] [--content-class photo|art] [--negative "..."] [--style <preset>]
```

- 認証情報は `.env` (`FIREFLY_CLIENT_ID`, `FIREFLY_CLIENT_SECRET`) から読む。未設定なら README の手順を案内する。
- 画像は `output/` に保存され、保存パスが標準出力に出る。生成後は Read で画像を確認してから結果を報告する。
- 詳しい手順は `.claude/commands/firefly.md` (`/firefly`) を参照。
