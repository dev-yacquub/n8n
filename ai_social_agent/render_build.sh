#!/usr/bin/env bash
set -e

echo "=== Installing Python dependencies ==="
pip install -r ai_social_agent/requirements.txt

echo "=== Installing Portable Node.js 20 ==="
NODE_VERSION="v20.18.0"
NODE_DIR="node-$NODE_VERSION-linux-x64"

if [ ! -d "$NODE_DIR" ]; then
    echo "Downloading Node.js $NODE_VERSION..."
    curl -fsSL "https://nodejs.org/dist/$NODE_VERSION/$NODE_DIR.tar.gz" | tar -xz
fi

export PATH="$PWD/$NODE_DIR/bin:$PATH"
echo "Node version: $(node -v)"
echo "NPM version: $(npm -v)"

echo "=== Installing WhatsApp Bridge dependencies ==="
cd ai_social_agent/whatsapp_bridge
npm install --omit=dev
echo "=== Build Complete ==="
