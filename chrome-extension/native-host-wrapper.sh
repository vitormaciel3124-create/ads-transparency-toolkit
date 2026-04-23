#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export HOME="/Users/vitormaciel"
export PLAYWRIGHT_BROWSERS_PATH=0

DIR="$(cd "$(dirname "$0")" && pwd)"
exec /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 "$DIR/native-host.py" 2>>"$DIR/native-host.log"
