import asyncio
import os
import logging
import json
from copilot import CopilotClient, PermissionHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Verify session persistence in the configured directory."""
    # Test path based on our persistent configuration
    config_dir = os.path.expanduser(
        "/app/backend/data/copilot"
        if os.path.exists("/app/backend/data")
        else "~/.copilot"
    )
    logger.info(f"Targeting config directory: {config_dir}")

    # Ensure it exists
    os.makedirs(config_dir, exist_ok=True)

    # copilot-sdk >= 1.0: CopilotClient takes kwargs directly; the config
    # directory is expressed via base_directory (sets COPILOT_HOME).
    client = CopilotClient(base_directory=config_dir)
    await client.start()

    try:
        # 1. Create a session
        logger.info("Creating a persistent session...")
        session = await client.create_session(
            on_permission_request=PermissionHandler.approve_all, model="gpt-4o"
        )
        chat_id = session.session_id
        logger.info(f"Session ID: {chat_id}")

        # 2. Verify file structure on host
        session_state_dir = os.path.join(config_dir, "session-state", chat_id)
        logger.info(f"Expected metadata path: {session_state_dir}")

        # We need to wait a bit for some meta-files to appear or just check if the directory was created
        if os.path.exists(session_state_dir):
            logger.info(f"✅ SUCCESS: Session state directory created in {config_dir}")
        else:
            logger.error(f"❌ ERROR: Session state directory NOT found in {config_dir}")

        # 3. Check for specific persistence files
        # history.json / snapshot.json are usually created by the CLI
        await asyncio.sleep(2)
        files = (
            os.listdir(session_state_dir) if os.path.exists(session_state_dir) else []
        )
        logger.info(f"Files found in metadata dir: {files}")

    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
