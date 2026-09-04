"""
Comprehensive Diagnostic and Testing Suite for SocialCommander AI Connectors.
Run from CLI to verify API tokens, endpoints, and credentials before launching.
"""

import sys
import asyncio
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
from ai_social_agent.connectors import (
    FacebookConnector,
    InstagramConnector,
    WhatsAppConnector,
    GmailConnector,
    SubstackConnector,
    N8NBridge
)
from ai_social_agent.core.agent_brain import agent_brain


async def test_all_connectors():
    print("=" * 65)
    print("  SocialCommander AI — Platform Connectivity Diagnostic")
    print("=" * 65)

    connectors = [
        ("Facebook Pages", FacebookConnector()),
        ("Instagram Business", InstagramConnector()),
        ("WhatsApp Cloud API", WhatsAppConnector()),
        ("Gmail", GmailConnector()),
        ("Substack", SubstackConnector()),
        ("n8n Bridge", N8NBridge())
    ]

    for name, conn in connectors:
        print(f"\nTesting {name}...")
        try:
            res = await conn.test_connection()
            status = "✅ PASS" if res.success else "⚠️ NOTICE"
            print(f"[{status}] {res.message}")
            if res.error and res.error != "UNCONFIGURED":
                print(f"  Error details: {res.error}")
        except Exception as e:
            print(f"[❌ FAIL] Exception: {str(e)}")

    print("\n" + "=" * 65)
    print("  Testing AI Brain & Tool Calling...")
    print("=" * 65)

    try:
        sample_prompt = "Qor maqaal gaaban oo Facebook ku saabsan faa'iidada AI ee waxbarashada"
        print(f"Prompt: {sample_prompt}")
        reply, pending = await agent_brain.process_user_message(
            chat_id=999999,
            user_text=sample_prompt
        )
        print("\nAI Response:")
        print(reply)
        if pending:
            print(f"\n[✅ STAGED ACTION DETECTED]: Platform={pending.platform}, Type={pending.action_type}")
    except Exception as e:
        print(f"[❌ LLM FAIL] Exception: {str(e)}")

    print("\nDiagnostic complete.\n")


if __name__ == "__main__":
    asyncio.run(test_all_connectors())
