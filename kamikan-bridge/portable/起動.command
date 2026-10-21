#!/bin/bash
set -u
PACKAGE_DIR="$(cd -- "$(dirname -- "$0")" && pwd)" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
cd -- "$PACKAGE_DIR" || exit 1
if ! command -v node >/dev/null 2>&1; then
  echo "初回だけNode.js 22以上のLTS版をインストールしてください。"
  echo "公式ページを開きます。インストール後に、この起動ファイルを開き直してください。"
  /usr/bin/open "https://nodejs.org/ja/download"
  read -r -p "Returnキーで閉じます。"
  exit 1
fi
node "$PACKAGE_DIR/bridge/portable/run.js"
RESULT=$?
if [ "$RESULT" -ne 0 ]; then
  echo "表示されたエラーを配布者へ伝えてください。"
  read -r -p "Returnキーで閉じます。"
fi
exit "$RESULT"
