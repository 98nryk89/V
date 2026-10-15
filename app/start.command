#!/bin/sh
# V アプリを起動する（Mac / Linux）。  ./app/start.sh
cd "$(dirname "$0")"
command -v node >/dev/null 2>&1 || { echo "Node.js が見つかりません。https://nodejs.org/ から LTS 版をインストールしてください。"; exit 1; }
(sleep 1; (command -v open >/dev/null && open http://localhost:8787/) || (command -v xdg-open >/dev/null && xdg-open http://localhost:8787/)) >/dev/null 2>&1 &
exec node server.mjs
