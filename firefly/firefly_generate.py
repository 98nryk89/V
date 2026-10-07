#!/usr/bin/env python3
"""Adobe Firefly Services API で画像を生成して保存する CLI.

依存ライブラリなし (Python 3.8+ 標準ライブラリのみ).

必要な環境変数 (または リポジトリ直下の .env):
  FIREFLY_CLIENT_ID      Adobe Developer Console の Client ID (API Key)
  FIREFLY_CLIENT_SECRET  同 Client Secret

使い方:
  python3 firefly/firefly_generate.py "夕焼けの富士山、水彩画風" -n 2 --size 1792x2304 --content-class art
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

IMS_TOKEN_URL = "https://ims-na1.adobelogin.com/ims/token/v3"
FIREFLY_BASE = "https://firefly-api.adobe.io"
SCOPES = "openid,AdobeID,session,additional_info,read_organizations,firefly_api,ff_apis"

# Firefly がサポートする出力サイズ
SIZES = {
    "square": (2048, 2048),
    "landscape": (2304, 1792),
    "portrait": (1792, 2304),
    "widescreen": (2688, 1536),
}

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def http(method, url, headers=None, data=None, timeout=120):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        sys.exit(f"HTTP {e.code} {method} {url}\n{body}")


def get_access_token(client_id, client_secret):
    form = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": SCOPES,
    }).encode()
    raw = http("POST", IMS_TOKEN_URL,
               {"Content-Type": "application/x-www-form-urlencoded"}, form)
    return json.loads(raw)["access_token"]


def parse_size(value):
    if value in SIZES:
        return SIZES[value]
    m = re.fullmatch(r"(\d+)x(\d+)", value)
    if not m:
        raise argparse.ArgumentTypeError(
            f"size は {', '.join(SIZES)} か WIDTHxHEIGHT で指定してください")
    return int(m.group(1)), int(m.group(2))


def slugify(text, limit=40):
    slug = re.sub(r"[^\w\-]+", "_", text, flags=re.UNICODE).strip("_")
    return slug[:limit] or "image"


def main():
    load_dotenv(REPO_ROOT / ".env")

    p = argparse.ArgumentParser(description="Adobe Firefly で画像を生成")
    p.add_argument("prompt", help="生成プロンプト (日本語可)")
    p.add_argument("-n", "--num", type=int, default=1, choices=range(1, 5),
                   help="生成枚数 1-4 (default: 1)")
    p.add_argument("--size", type=parse_size, default="square",
                   help="square|landscape|portrait|widescreen または WIDTHxHEIGHT")
    p.add_argument("--content-class", choices=["photo", "art"],
                   help="写真風(photo) / アート風(art)")
    p.add_argument("--negative", help="含めたくない要素 (negativePrompt)")
    p.add_argument("--style", action="append", default=[],
                   help="スタイルプリセット (例: watercolor, anime)。複数指定可")
    p.add_argument("--locale", default="ja-JP", help="プロンプトのロケール (default: ja-JP)")
    p.add_argument("--seed", type=int, action="append", help="シード値 (再現用、複数指定可)")
    p.add_argument("--model", help="x-model-version (例: image4_standard, image3)")
    p.add_argument("-o", "--out-dir", default=str(REPO_ROOT / "output"),
                   help="保存先ディレクトリ (default: ./output)")
    args = p.parse_args()

    client_id = os.environ.get("FIREFLY_CLIENT_ID")
    client_secret = os.environ.get("FIREFLY_CLIENT_SECRET")
    if not client_id or not client_secret:
        sys.exit("FIREFLY_CLIENT_ID / FIREFLY_CLIENT_SECRET が未設定です (.env.example を参照)")

    width, height = args.size
    body = {
        "prompt": args.prompt,
        "numVariations": args.num,
        "size": {"width": width, "height": height},
        "promptBiasingLocaleCode": args.locale,
    }
    if args.content_class:
        body["contentClass"] = args.content_class
    if args.negative:
        body["negativePrompt"] = args.negative
    if args.style:
        body["style"] = {"presets": args.style}
    if args.seed:
        body["seeds"] = args.seed

    token = get_access_token(client_id, client_secret)
    headers = {
        "Authorization": f"Bearer {token}",
        "x-api-key": client_id,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if args.model:
        headers["x-model-version"] = args.model

    print(f"Firefly に送信中: {args.prompt!r} ({width}x{height}, {args.num}枚)", file=sys.stderr)
    job = json.loads(http("POST", f"{FIREFLY_BASE}/v3/images/generate-async",
                          headers, json.dumps(body).encode()))
    status_url = job["statusUrl"]

    # 非同期ジョブをポーリング
    deadline = time.time() + 300
    while True:
        time.sleep(2)
        status = json.loads(http("GET", status_url, headers))
        state = status.get("status")
        if state == "succeeded":
            break
        if state in ("failed", "canceled", "cancelled"):
            sys.exit(f"生成に失敗しました: {json.dumps(status, ensure_ascii=False)}")
        if time.time() > deadline:
            sys.exit("タイムアウトしました (5分)")

    outputs = status.get("result", {}).get("outputs", [])
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    saved = []
    for i, out in enumerate(outputs, 1):
        url = out["image"]["url"]
        ext = ".png" if ".png" in urllib.parse.urlparse(url).path else ".jpg"
        path = out_dir / f"{stamp}_{slugify(args.prompt)}_{i}{ext}"
        path.write_bytes(http("GET", url))
        saved.append({"path": str(path), "seed": out.get("seed")})

    meta = {"prompt": args.prompt, "request": body, "images": saved}
    (out_dir / f"{stamp}_{slugify(args.prompt)}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    for s in saved:
        print(s["path"])


if __name__ == "__main__":
    main()
