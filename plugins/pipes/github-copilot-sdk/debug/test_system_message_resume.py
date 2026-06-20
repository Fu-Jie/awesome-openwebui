#!/usr/bin/env python3
"""
Copilot SDK System Message Test Script
Tests whether system_message is properly applied during session.resume

This script verifies the bug hypothesis:
- session.resume with system_message config may not reliably update the system prompt

Test scenarios:
1. Create a new session with a custom system message
2. Resume the same session with a DIFFERENT system message
3. Ask the model to describe its current system instructions

Requirements:
- github-copilot-sdk>=0.1.23
"""

import asyncio
import os
import sys
import time

from copilot import CopilotClient
from copilot.types import SessionConfig
from copilot.generated.session_events import SessionEventType


# Test system messages
SYSTEM_MSG_A = """You are a helpful assistant named "ALPHA". 
When asked about your name or identity, you MUST respond: "I am ALPHA, the first assistant."
Always start your responses with "[ALPHA]:" prefix.
"""

SYSTEM_MSG_B = """You are a helpful assistant named "BETA". 
When asked about your name or identity, you MUST respond: "I am BETA, the second assistant."
Always start your responses with "[BETA]:" prefix.
"""


async def send_and_get_response(session, prompt: str) -> str:
    """Send a message and collect the full response using event subscription."""
    full_response = ""
    response_complete = asyncio.Event()

    def event_handler(event):
        nonlocal full_response
        if event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA:
            delta = getattr(event.data, "content", "") or ""
            print(delta, end="", flush=True)
            full_response += delta
        elif event.type == SessionEventType.ASSISTANT_MESSAGE:
            # Final complete message
            content = getattr(event.data, "content", "") or ""
            if content and not full_response:
                full_response = content
                print(content, end="", flush=True)
        elif event.type == SessionEventType.SESSION_IDLE:
            response_complete.set()
        elif event.type == SessionEventType.ASSISTANT_TURN_END:
            response_complete.set()

    # Subscribe to events
    unsubscribe = session.on(event_handler)

    try:
        # Send the message
        await session.send({"prompt": prompt, "mode": "immediate"})
        # Wait for completion (with timeout)
        await asyncio.wait_for(response_complete.wait(), timeout=120)
        print()  # newline after completion
    finally:
        unsubscribe()

    return full_response


async def test_new_session_system_message(client: CopilotClient):
    """Test 1: New session with system message A"""
    print("\n" + "=" * 60)
    print("TEST 1: New Session with System Message A (ALPHA)")
    print("=" * 60)

    session_config = SessionConfig(
        session_id="test-session-001",
        model="gpt-5-mini",
        streaming=True,
        system_message={
            "mode": "replace",
            "content": SYSTEM_MSG_A,
        },
    )

    session = await client.create_session(config=session_config)
    print(f"✅ Created new session: {session.session_id}")

    print("\n📤 Asking: 'What is your name?'")
    print("📥 Response: ", end="")
    response = await send_and_get_response(session, "What is your name?")

    if "ALPHA" in response:
        print("✅ SUCCESS: Model correctly identified as ALPHA")
    else:
        print("⚠️ WARNING: Model did NOT identify as ALPHA")

    return session


async def test_resume_session_with_new_system_message(
    client: CopilotClient, session_id: str
):
    """Test 2: Resume session with DIFFERENT system message B"""
    print("\n" + "=" * 60)
    print("TEST 2: Resume Session with System Message B (BETA)")
    print("=" * 60)

    resume_config = {
        "model": "gpt-5-mini",
        "streaming": True,
        "system_message": {
            "mode": "replace",
            "content": SYSTEM_MSG_B,
        },
    }

    print(f"📋 Resume config includes system_message with mode='replace'")
    print(f"📋 New system_message content: BETA identity")

    session = await client.resume_session(session_id, resume_config)
    print(f"✅ Resumed session: {session.session_id}")

    print("\n📤 Asking: 'What is your name now? Did your identity change?'")
    print("📥 Response: ", end="")
    response = await send_and_get_response(
        session, "What is your name now? Did your identity change?"
    )

    if "BETA" in response:
        print("✅ SUCCESS: System message was updated to BETA")
        return True
    elif "ALPHA" in response:
        print("❌ BUG CONFIRMED: System message was NOT updated (still ALPHA)")
        return False
    else:
        print("⚠️ INCONCLUSIVE: Model response doesn't clearly indicate identity")
        return None


async def test_resume_without_system_message(client: CopilotClient, session_id: str):
    """Test 3: Resume session without specifying system_message"""
    print("\n" + "=" * 60)
    print("TEST 3: Resume Session WITHOUT System Message")
    print("=" * 60)

    resume_config = {
        "model": "gpt-4o",
        "streaming": True,
        # No system_message specified
    }

    session = await client.resume_session(session_id, resume_config)
    print(f"✅ Resumed session: {session.session_id}")

    print("\n📤 Asking: 'What is your name? Tell me your current identity.'")
    print("📥 Response: ", end="")
    response = await send_and_get_response(
        session, "What is your name? Tell me your current identity."
    )

    if "ALPHA" in response:
        print(
            "ℹ️ Without system_message: Model still remembers ALPHA from original session"
        )
    elif "BETA" in response:
        print("ℹ️ Without system_message: Model remembers BETA from Test 2")
    else:
        print("ℹ️ Model identity unclear")


async def main():
    print("=" * 60)
    print("🧪 Copilot SDK System Message Resume Test")
    print("=" * 60)
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Testing with SDK from: {CopilotClient.__module__}")

    # Create client with explicit CLI path if provided
    cli_path = os.environ.get("COPILOT_CLI_PATH")
    client_config = {"log_level": "info"}
    if cli_path:
        # copilot-sdk >= 1.0: cli_path is expressed via a StdioRuntimeConnection.
        from copilot.client import StdioRuntimeConnection

        client_config["connection"] = StdioRuntimeConnection(path=cli_path)

    client = CopilotClient(**client_config)

    try:
        await client.start()
        print("✅ Client started successfully")

        # Test 1: Create new session with system message A
        session = await test_new_session_system_message(client)
        session_id = session.session_id

        # Wait a bit before resuming
        print("\n⏳ Waiting 2 seconds before resume test...")
        await asyncio.sleep(2)

        # Test 2: Resume with different system message B
        bug_confirmed = await test_resume_session_with_new_system_message(
            client, session_id
        )

        # Test 3: Resume without system message
        await test_resume_without_system_message(client, session_id)

        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY (Native Copilot)")
        print("=" * 60)
        if bug_confirmed is False:
            print(
                "❌ BUG CONFIRMED: session.resume does NOT apply system_message updates"
            )
            print("   The system message from create_session persists even when")
            print("   resume_session specifies a different system_message.")
            print("\n   WORKAROUND: Inject system context into user prompt instead.")
        elif bug_confirmed is True:
            print("✅ NO BUG: session.resume correctly updates system_message")
        else:
            print("⚠️ INCONCLUSIVE: Could not determine if bug exists")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await client.stop()
        print("\n✅ Client stopped")


# =============================================================================
# BYOK OpenAI Test
# =============================================================================


async def test_byok_new_session(client: CopilotClient, provider_config: dict):
    """BYOK Test 1: New session with BYOK provider and system message A"""
    print("\n" + "=" * 60)
    print("BYOK TEST 1: New Session with BYOK Provider + System Message A (ALPHA)")
    print("=" * 60)
    print(
        f"📋 Provider: {provider_config.get('type')} @ {provider_config.get('base_url')}"
    )

    session_config = SessionConfig(
        session_id="byok-test-session-001",
        model="gpt-4o",  # or your model name
        streaming=True,
        provider=provider_config,
        system_message={
            "mode": "replace",
            "content": SYSTEM_MSG_A,
        },
    )

    session = await client.create_session(config=session_config)
    print(f"✅ Created BYOK session: {session.session_id}")

    print("\n📤 Asking: 'What is your name?'")
    print("📥 Response: ", end="")
    response = await send_and_get_response(session, "What is your name?")

    if "ALPHA" in response:
        print("✅ SUCCESS: Model correctly identified as ALPHA")
    else:
        print("⚠️ WARNING: Model did NOT identify as ALPHA")

    return session


async def test_byok_resume_with_new_system_message(
    client: CopilotClient, session_id: str, provider_config: dict
):
    """BYOK Test 2: Resume BYOK session with DIFFERENT system message B"""
    print("\n" + "=" * 60)
    print("BYOK TEST 2: Resume BYOK Session with System Message B (BETA)")
    print("=" * 60)

    resume_config = {
        "model": "gpt-4o",
        "streaming": True,
        "provider": provider_config,
        "system_message": {
            "mode": "replace",
            "content": SYSTEM_MSG_B,
        },
    }

    print(f"📋 Resume config includes system_message with mode='replace'")
    print(f"📋 New system_message content: BETA identity")
    print(
        f"📋 Provider: {provider_config.get('type')} @ {provider_config.get('base_url')}"
    )

    session = await client.resume_session(session_id, resume_config)
    print(f"✅ Resumed BYOK session: {session.session_id}")

    print("\n📤 Asking: 'What is your name now? Did your identity change?'")
    print("📥 Response: ", end="")
    response = await send_and_get_response(
        session, "What is your name now? Did your identity change?"
    )

    if "BETA" in response:
        print("✅ SUCCESS: System message was updated to BETA")
        return True
    elif "ALPHA" in response:
        print("❌ BUG CONFIRMED: System message was NOT updated (still ALPHA)")
        return False
    else:
        print("⚠️ INCONCLUSIVE: Model response doesn't clearly indicate identity")
        return None


async def main_byok():
    """Run BYOK-specific tests"""
    print("=" * 60)
    print("🧪 Copilot SDK BYOK System Message Resume Test")
    print("=" * 60)
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Get BYOK configuration from environment
    byok_api_key = os.environ.get("BYOK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    byok_base_url = os.environ.get("BYOK_BASE_URL", "https://api.openai.com/v1")
    byok_model = os.environ.get("BYOK_MODEL", "gpt-4o")

    if not byok_api_key:
        print(
            "❌ Error: Please set BYOK_API_KEY or OPENAI_API_KEY environment variable"
        )
        print("   export BYOK_API_KEY='your_api_key'")
        print("   export BYOK_BASE_URL='https://api.openai.com/v1'  # optional")
        print("   export BYOK_MODEL='gpt-4o'  # optional")
        return

    provider_config = {
        "type": "openai",
        "base_url": byok_base_url,
        "api_key": byok_api_key,
    }

    print(f"📋 BYOK Provider: openai @ {byok_base_url}")
    print(f"📋 BYOK Model: {byok_model}")

    # Create client
    cli_path = os.environ.get("COPILOT_CLI_PATH")
    client_config = {"log_level": "info"}
    if cli_path:
        # copilot-sdk >= 1.0: cli_path is expressed via a StdioRuntimeConnection.
        from copilot.client import StdioRuntimeConnection

        client_config["connection"] = StdioRuntimeConnection(path=cli_path)

    client = CopilotClient(**client_config)

    try:
        await client.start()
        print("✅ Client started successfully")

        # BYOK Test 1: Create new session with BYOK provider
        session = await test_byok_new_session(client, provider_config)
        session_id = session.session_id

        # Wait a bit before resuming
        print("\n⏳ Waiting 2 seconds before resume test...")
        await asyncio.sleep(2)

        # BYOK Test 2: Resume with different system message B
        bug_confirmed = await test_byok_resume_with_new_system_message(
            client, session_id, provider_config
        )

        # Summary
        print("\n" + "=" * 60)
        print("📊 BYOK TEST SUMMARY")
        print("=" * 60)
        if bug_confirmed is False:
            print(
                "❌ BYOK BUG CONFIRMED: session.resume does NOT apply system_message updates"
            )
            print("   In BYOK mode, the system message from create_session persists")
            print("   even when resume_session specifies a different system_message.")
            print("\n   WORKAROUND: Inject system context into user prompt instead.")
        elif bug_confirmed is True:
            print("✅ BYOK NO BUG: session.resume correctly updates system_message")
        else:
            print("⚠️ BYOK INCONCLUSIVE: Could not determine if bug exists")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await client.stop()
        print("\n✅ Client stopped")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Copilot SDK System Message Resume Test"
    )
    parser.add_argument(
        "--byok",
        action="store_true",
        help="Run BYOK (Bring Your Own Key) test instead of native Copilot test",
    )
    args = parser.parse_args()

    if args.byok:
        print("Running BYOK test mode...")
        asyncio.run(main_byok())
    else:
        print("Running native Copilot test mode...")
        print("(Use --byok flag for BYOK provider test)")
        asyncio.run(main())
