import requests
import json
import os
import re
from pathlib import Path

# ─── Configuration ───────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
ENV_FILE = SCRIPT_DIR / ".env"

URL = (
    "http://localhost:3003/api/v1/functions/id/github_copilot_official_sdk_pipe/update"
)
FILE_PATH = SCRIPT_DIR.parent / "plugins/pipes/github-copilot-sdk/github_copilot_sdk.py"


def _load_api_key() -> str:
    """Load API key from .env file in the same directory as this script.

    The .env file should contain a line like:
        api_key=sk-xxxxxxxxxxxx
    """
    if not ENV_FILE.exists():
        raise FileNotFoundError(
            f".env file not found at {ENV_FILE}. "
            "Please create it with: api_key=sk-xxxxxxxxxxxx"
        )

    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("api_key="):
            key = line.split("=", 1)[1].strip()
            if key:
                return key

    raise ValueError("api_key not found in .env file.")


def deploy_pipe() -> None:
    """Push the latest local github_copilot_sdk.py content to OpenWebUI."""
    # 1. Load API key
    try:
        api_key = _load_api_key()
    except (FileNotFoundError, ValueError) as e:
        print(f"[ERROR] {e}")
        return

    # 2. Read local source file
    if not FILE_PATH.exists():
        print(f"[ERROR] Source file not found: {FILE_PATH}")
        return

    content = FILE_PATH.read_text(encoding="utf-8")

    # 3. Extract version from docstring
    version_match = re.search(r"version:\s*([\d.]+)", content)
    version = version_match.group(1) if version_match else "0.9.0"

    # 4. Build payload
    payload = {
        "id": "github_copilot_official_sdk_pipe",
        "name": "GitHub Copilot Official SDK Pipe",
        "meta": {
            "description": (
                "Integrate GitHub Copilot SDK. Supports dynamic models, "
                "multi-turn conversation, streaming, multimodal input, "
                "infinite sessions, and frontend debug logging."
            ),
            "manifest": {
                "title": "GitHub Copilot Official SDK Pipe",
                "author": "Fu-Jie",
                "author_url": "https://github.com/Fu-Jie/openwebui-extensions",
                "funding_url": "https://github.com/open-webui",
                "openwebui_id": "ce96f7b4-12fc-4ac3-9a01-875713e69359",
                "description": (
                    "Integrate GitHub Copilot SDK. Supports dynamic models, "
                    "multi-turn conversation, streaming, multimodal input, "
                    "infinite sessions, bidirectional OpenWebUI Skills bridge, "
                    "and manage_skills tool."
                ),
                "version": version,
                "requirements": "github-copilot-sdk==1.0.2",
            },
            "type": "pipe",
        },
        "content": content,
    }

    # 5. Build headers — use long-lived API key instead of short-lived JWT
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    # 6. Send update request
    print(f"Updating pipe with version {version}...")
    try:
        response = requests.post(URL, headers=headers, data=json.dumps(payload))
        if response.status_code == 200:
            print("✅ Successfully updated GitHub Copilot Official SDK Pipe!")
        else:
            print(
                f"⚠️ Update failed with status {response.status_code}, attempting to create instead..."
            )
            CREATE_URL = "http://localhost:3003/api/v1/functions/create"
            res_create = requests.post(
                CREATE_URL, headers=headers, data=json.dumps(payload)
            )
            if res_create.status_code == 200:
                print("✅ Successfully created GitHub Copilot Official SDK Pipe!")
            else:
                print(
                    f"❌ Failed to update or create. Status: {res_create.status_code}"
                )
                print(f"   Response: {res_create.text[:500]}")
    except Exception as e:
        print(f"❌ Request error: {e}")


if __name__ == "__main__":
    deploy_pipe()
