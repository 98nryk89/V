#!/bin/sh
# Install what the build/preview tools need. Browser: use an existing Chromium (do NOT run `playwright install` in
# sandboxes); tools/preview.py looks for /opt/pw-browsers/chromium-*/chrome-linux/chrome, else set CHROME_PATH.
pip install -r "$(dirname "$0")/../requirements.txt"
