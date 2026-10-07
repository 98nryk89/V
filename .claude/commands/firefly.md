---
description: Adobe Firefly で画像を生成する
argument-hint: <作りたい画像の説明>
allowed-tools: Bash(python3 firefly/firefly_generate.py:*), Read
---

ユーザーの依頼: $ARGUMENTS

Adobe Firefly で上記の画像を生成してください。手順:

1. 依頼内容から Firefly 向けの具体的なプロンプトを作る (被写体・構図・光・質感・画風を補う。日本語のままで可)。
2. 依頼に合わせてオプションを選ぶ:
   - 写真風なら `--content-class photo`、イラスト・絵画なら `--content-class art`
   - 横長は `--size landscape`、縦長は `--size portrait`、16:9 は `--size widescreen`
   - 枚数指定があれば `-n`、避けたい要素があれば `--negative`
3. 実行: `python3 firefly/firefly_generate.py "<プロンプト>" [オプション]`
4. 出力された画像パスを Read で開いて確認し、使ったプロンプトと保存先をユーザーに伝える。
   イメージと違えばプロンプトを調整して再生成を提案する。
