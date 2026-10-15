@echo off
chcp 65001 >nul
cd /d %~dp0
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js が見つかりません。https://nodejs.org/ から LTS 版をインストールしてください。
  pause
  exit /b 1
)
start "" http://localhost:8787/
node server.mjs
pause
