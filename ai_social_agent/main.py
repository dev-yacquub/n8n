"""
Main Entry Point for AI Social Media & Communications Master Agent.
Runs the Telegram Bot Service.
"""

import sys
import asyncio
import logging
from pathlib import Path

# Fix Windows console UTF-8 encoding for emojis
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR.parent) not in sys.path:
    sys.path.insert(0, str(BASE_DIR.parent))

from ai_social_agent.config.config import config
from ai_social_agent.core.bot import build_application

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("SocialCommander.Main")


import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler


import urllib.request
import urllib.error


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/qr":
            try:
                req = urllib.request.Request("http://127.0.0.1:3001/qr")
                with urllib.request.urlopen(req, timeout=5) as response:
                    content = response.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(content)
            except Exception as e:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                html = f"""
                <html>
                    <head><title>WhatsApp Bridge Starting</title><meta http-equiv="refresh" content="3"></head>
                    <body style="font-family: sans-serif; display:flex; flex-direction:column; align-items:center; justify-content:center; height:100vh; background:#0f172a; color:#f8fafc;">
                        <h2>WhatsApp Bridge is starting up...</h2>
                        <p style="color:#94a3b8;">Auto-refreshing in 3 seconds...</p>
                    </body>
                </html>
                """
                self.wfile.write(html.encode("utf-8"))
        elif self.path == "/status":
            try:
                req = urllib.request.Request("http://127.0.0.1:3001/status")
                with urllib.request.urlopen(req, timeout=5) as response:
                    content = response.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(content)
            except Exception as e:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"success": false, "connected": false, "error": "Bridge offline"}')
        elif self.path.startswith("/media/"):
            clean_path = self.path.split("?")[0]
            filename = os.path.basename(clean_path)
            file_path = os.path.join(str(config.UPLOADS_DIR), filename)
            if not os.path.exists(file_path):
                file_path = os.path.join(str(BASE_DIR), "uploads", filename)
            if not os.path.exists(file_path):
                file_path = os.path.join(os.getcwd(), "uploads", filename)
            if os.path.exists(file_path):
                try:
                    with open(file_path, "rb") as f:
                        content = f.read()
                    self.send_response(200)
                    if filename.lower().endswith(".png"):
                        self.send_header("Content-Type", "image/png")
                    elif filename.lower().endswith((".jpg", ".jpeg")):
                        self.send_header("Content-Type", "image/jpeg")
                    else:
                        self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                except Exception:
                    self.send_response(500)
                    self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok","service":"SocialCommander AI Agent"}')

    def log_message(self, format, *args):
        pass  # Suppress access logs


def start_health_server():
    port_str = os.getenv("PORT", "10000").strip()
    port = int(port_str) if port_str.isdigit() else 10000
    try:
        HTTPServer.allow_reuse_address = True
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        print(f"📡 Cloud Health Check & QR Server listening on 0.0.0.0:{port}", flush=True)
    except Exception as e:
        print(f"⚠️ Could not start health check server: {e}", flush=True)


def main():
    start_health_server()
    print("=" * 70)
    print(" 🚀 SocialCommander AI — Multi-Platform Master Executive Agent")
    print("=" * 70)
    print(f" • Telegram Bot Token: {'***' + config.TELEGRAM_BOT_TOKEN[-6:] if config.TELEGRAM_BOT_TOKEN else 'MISSING'}")
    print(f" • LLM Provider: {config.LLM_PROVIDER} ({config.LLM_MODEL})")

    summary = config.get_status_summary()
    print("\n Platform Readiness:")
    for plat, ready in summary.items():
        status = "✅ Configured" if ready else "⚠️ Missing Credentials"
        print(f"   - {plat.capitalize():<12}: {status}")
    print("=" * 70)

    if not config.TELEGRAM_BOT_TOKEN:
        print("\n❌ Error: TELEGRAM_BOT_TOKEN must be configured in .env before starting.")
        sys.exit(1)

    print("\nStarting Telegram Bot with long-polling...")
    app = build_application()
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
