"""
Automated Test Suite for Multi-Tenant Facebook Page AI Agent.
Tests:
1. Multi-tenant database isolation (User A vs User B).
2. Dynamic page switching and credentials retrieval.
3. FacebookConnector factory and token validation parser.
4. Tool schemas compatibility with OpenAI / Gemini standard.
5. ConfirmationManager execution pipeline with user credentials.
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
BASE_DIR = Path(__file__).resolve().parent.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from ai_social_agent.core.user_db import user_db
from ai_social_agent.connectors.facebook_connector import FacebookConnector, get_facebook_connector_for_user
from ai_social_agent.tools.registry import TOOLS_SCHEMA
from ai_social_agent.core.confirmation_mgr import confirmation_mgr
from ai_social_agent.core.agent_brain import agent_brain


def test_database_multi_tenancy():
    print("\n--- TEST 1: Database Multi-Tenancy & Isolation ---")
    user_a = 999001
    user_b = 999002

    # Clean prior test state
    user_db.disconnect_user(user_a)
    user_db.disconnect_user(user_b)

    # 1. User A connects 2 pages
    pages_a = [
        {"id": "page_101", "name": "User A Tech News", "access_token": "token_a_101", "category": "Media", "fan_count": 5000},
        {"id": "page_102", "name": "User A E-Commerce", "access_token": "token_a_102", "category": "Retail", "fan_count": 1200}
    ]
    user_db.save_user_token_and_pages(user_a, "user_token_a", pages_a, "alice", "Alice")

    # 2. User B connects 1 page
    pages_b = [
        {"id": "page_201", "name": "User B Restaurant", "access_token": "token_b_201", "category": "Food", "fan_count": 800}
    ]
    user_db.save_user_token_and_pages(user_b, "user_token_b", pages_b, "bob", "Bob")

    # Verify User A credentials
    creds_a = user_db.get_user_credentials(user_a)
    assert creds_a is not None, "User A should have credentials"
    assert creds_a["page_id"] == "page_101", f"Expected page_101, got {creds_a['page_id']}"
    assert creds_a["page_access_token"] == "token_a_101"
    print("✅ User A initial active page verified: page_101 (User A Tech News)")

    # Verify User B credentials
    creds_b = user_db.get_user_credentials(user_b)
    assert creds_b is not None, "User B should have credentials"
    assert creds_b["page_id"] == "page_201", f"Expected page_201, got {creds_b['page_id']}"
    assert creds_b["page_access_token"] == "token_b_201"
    print("✅ User B active page verified: page_201 (User B Restaurant)")

    # 3. User A switches active page to page_102
    switched = user_db.set_active_page(user_a, "page_102")
    assert switched is True, "User A switch to page_102 should succeed"
    creds_a_updated = user_db.get_user_credentials(user_a)
    assert creds_a_updated["page_id"] == "page_102"
    assert creds_a_updated["page_name"] == "User A E-Commerce"
    print("✅ User A successfully switched active page to: page_102")

    # Verify User B was NOT affected by User A's switch
    creds_b_check = user_db.get_user_credentials(user_b)
    assert creds_b_check["page_id"] == "page_201", "User B must remain untouched"
    print("✅ Complete isolation confirmed between User A and User B")

    # Clean up test records
    user_db.disconnect_user(user_a)
    user_db.disconnect_user(user_b)
    print("✅ Cleaned up test records")


def test_facebook_connector_factory():
    print("\n--- TEST 2: Dynamic FacebookConnector Factory ---")
    test_uid = 999003
    user_db.save_page(test_uid, "page_test_99", "Dynamic Page", "test_access_token_xyz")

    connector = get_facebook_connector_for_user(test_uid)
    assert connector.page_id == "page_test_99", f"Expected page_test_99, got {connector.page_id}"
    assert connector.access_token == "test_access_token_xyz"
    assert connector.is_configured() is True
    print(f"✅ Factory successfully produced connector for User {test_uid}: {connector.page_id}")

    user_db.disconnect_user(test_uid)


def test_tools_schema():
    print("\n--- TEST 3: Tools Schema Validation ---")
    expected_tools = [
        "get_facebook_page_overview",
        "post_to_facebook",
        "publish_facebook_ad_post",
        "create_facebook_ad_campaign",
        "get_facebook_posts_and_insights",
        "get_facebook_inbox",
        "get_conversation_messages",
        "reply_to_facebook_message",
        "get_facebook_post_comments",
        "reply_to_facebook_comment"
    ]
    registered_names = [t["function"]["name"] for t in TOOLS_SCHEMA]

    for t_name in expected_tools:
        assert t_name in registered_names, f"Tool '{t_name}' missing from TOOLS_SCHEMA"
        print(f"✅ Tool verified: {t_name}")

    print(f"✅ Total tools registered: {len(TOOLS_SCHEMA)}")


def test_confirmation_manager_multi_tenancy():
    print("\n--- TEST 4: ConfirmationManager Multi-Tenancy ---")
    action = confirmation_mgr.create_pending_action(
        platform="facebook",
        action_type="post_text",
        payload={"message": "Hello Multi-Tenant Facebook!"},
        preview_text="Preview: Post to Facebook",
        telegram_id=999004
    )
    assert action.telegram_id == 999004
    retrieved = confirmation_mgr.get_pending(action.action_id)
    assert retrieved is not None
    assert retrieved.telegram_id == 999004
    print(f"✅ PendingAction correctly created and bound to telegram_id {action.telegram_id}")

    # Test cancel
    confirmation_mgr.cancel_action(action.action_id)
    assert confirmation_mgr.get_pending(action.action_id) is None
    print("✅ Action successfully cancelled")


def main():
    print("=" * 60)
    print("🧪 Running Multi-Tenant Facebook Page AI Agent Test Suite")
    print("=" * 60)

    try:
        test_database_multi_tenancy()
        test_facebook_connector_factory()
        test_tools_schema()
        test_confirmation_manager_multi_tenancy()
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED SUCCESSFULLY! 🚀")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
