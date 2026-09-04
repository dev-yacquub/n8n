#!/bin/bash
set -e

echo "=================================================="
echo " 🚀 Starting SocialCommander AI Cloud Services"
echo "=================================================="

# Start WhatsApp Baileys Bridge in background
echo "Starting WhatsApp Linked Device Bridge on port 3001..."
cd /app/ai_social_agent/whatsapp_bridge
node index.js &
BRIDGE_PID=$!

cd /app

# Give bridge a moment to initialize
sleep 2

# Start Python SocialCommander Agent
echo "Starting Python SocialCommander Agent..."
python ai_social_agent/main.py
