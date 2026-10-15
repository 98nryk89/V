#!/bin/sh
# usage: tools/rebuild.sh projects/<name>  -> rebuilds out/ (parts, rig.json)
cd "$(dirname "$0")/.." && python3 -I -c "
import sys; sys.path.insert(0,'.')
from live2d_ai.build import build
build('$1', verbose=False)"
