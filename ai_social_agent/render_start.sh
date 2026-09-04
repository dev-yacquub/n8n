#!/usr/bin/env bash
set -e

NODE_VERSION="v20.18.0"
NODE_DIR="node-$NODE_VERSION-linux-x64"
export PATH="$PWD/$NODE_DIR/bin:$PATH"

echo "=== Starting WhatsApp Bridge (port 3001) ==="
cd ai_social_agent/whatsapp_bridge
node index.js &
cd ../..

sleep 2

echo "=== Starting SocialCommander Python Agent (port ${PORT:-10000}) ==="
exec python ai_social_agent/main.py
