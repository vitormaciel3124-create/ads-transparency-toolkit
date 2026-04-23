#!/bin/bash
# Installer for Ads Transparency Downloader native messaging host.
# Run after loading the extension in Chrome to get the extension ID.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOST_NAME="com.cv.ads_downloader"
HOST_PATH="$SCRIPT_DIR/native-host.py"

# Chrome native messaging host directory
NM_DIR="$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts"
mkdir -p "$NM_DIR"

if [ -z "$1" ]; then
    echo ""
    echo "Usage: ./install.sh <chrome-extension-id>"
    echo ""
    echo "Steps:"
    echo "  1. Open Chrome → chrome://extensions"
    echo "  2. Enable 'Developer mode' (toggle top right)"
    echo "  3. Click 'Load unpacked' → select this folder:"
    echo "     $SCRIPT_DIR"
    echo "  4. Copy the extension ID shown (e.g. abcdefghijklmnop...)"
    echo "  5. Run: ./install.sh <that-id>"
    echo ""
    exit 1
fi

EXT_ID="$1"

# Write native messaging host manifest
cat > "$NM_DIR/$HOST_NAME.json" << EOF
{
  "name": "$HOST_NAME",
  "description": "Ads Transparency video downloader",
  "path": "$HOST_PATH",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://$EXT_ID/"
  ]
}
EOF

echo "Native messaging host installed!"
echo "  Manifest: $NM_DIR/$HOST_NAME.json"
echo "  Host:     $HOST_PATH"
echo "  Extension ID: $EXT_ID"
echo ""
echo "Now go to an Ads Transparency video page and click the download button!"
