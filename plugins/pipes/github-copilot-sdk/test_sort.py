#!/usr/bin/env python3
"""
Standalone test for GitHub Copilot SDK model sorting.
Makes REAL API calls to BYOK endpoint and Copilot SDK.
"""
import os, asyncio, aiohttp, logging, json
from typing import List, Dict
from collections import Counter

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

GH_TOKEN = os.getenv("GH_TOKEN", "")
BYOK_BASE_URL = os.getenv("BYOK_BASE_URL", "")
BYOK_API_KEY = os.getenv("BYOK_API_KEY", "")
BYOK_BEARER_TOKEN = os.getenv("BYOK_BEARER_TOKEN", "")
BYOK_TYPE = os.getenv("BYOK_TYPE", "")  # openai | anthropic | google
BYOK_MODELS = os.getenv("BYOK_MODELS", "")

PROVIDER_ORDER = {"openai": 0, "anthropic": 1, "google": 2, "unknown": 3}


# ── Infer provider from model ID ───────────────────────────────────────────────
def infer_provider(mid: str) -> str:
    """Infer provider from model ID string (same logic as in real pipe)."""
    id_lower = mid.lower()
    if any(k in id_lower for k in ["gpt", "codex", "o1", "o3", "o4", "chatgpt"]):
        return "openai"
    if any(k in id_lower for k in ["claude", "anthropic"]):
        return "anthropic"
    if any(k in id_lower for k in ["gemini", "aistudio", "vertex"]):
        return "google"
    if any(
        k in id_lower
        for k in ["qwen", "qwen3", "qwq", "deepseek", "mistral", "mixtral", "llama"]
    ):
        return "openai"
    if "/" in mid:  # OpenRouter format: provider/model
        return "openai"
    return "unknown"


# ── 1. Copilot SDK (real) ─────────────────────────────────────────────────────
async def fetch_copilot(token: str) -> List[Dict]:
    if not token:
        logger.warning("GH_TOKEN not set — skipping Copilot SDK")
        return []
    try:
        from copilot import CopilotClient
    except ImportError as e:
        logger.error(f"Import error: {e}")
        return []

    try:
        # copilot-sdk >= 1.0: SubprocessConfig removed; pass kwargs directly.
        client = CopilotClient(
            github_token=token, use_logged_in_user=False
        )
        await client.start()
        raw = await client.list_models()
        logger.info(
            f"Copilot SDK returned {len(raw) if hasattr(raw,'__len__') else '?'} models"
        )

        models = []
        for m in raw if isinstance(raw, list) else []:
            mid = m.get("id") if isinstance(m, dict) else getattr(m, "id", "")
            bill = (
                m.get("billing") if isinstance(m, dict) else getattr(m, "billing", {})
            )
            if hasattr(bill, "to_dict"):
                bill = bill.to_dict()
            mult = float(bill.get("multiplier", 1.0)) if isinstance(bill, dict) else 1.0
            provider = infer_provider(mid)
            models.append(
                {
                    "id": f"github_copilot_sdk-{mid}",
                    "name": f"-{mid} ({mult}x)" if mult > 0 else f"-🔥 {mid} (0x)",
                    "multiplier": mult,
                    "raw_id": mid,
                    "source": "copilot",
                    "provider": provider,
                }
            )
        return models
    except Exception as e:
        logger.error(f"Copilot SDK failed: {e}", exc_info=True)
        return []


# ── 2. BYOK API (real) ────────────────────────────────────────────────────────
async def fetch_byok(
    base_url: str, byok_type: str, api_key: str, bearer_token: str
) -> List[Dict]:
    if not base_url:
        return []
    try:
        base_url = base_url.rstrip("/")
        url = f"{base_url}/models"
        headers, pt = {}, byok_type.lower()
        if pt == "anthropic":
            if api_key:
                headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
        else:
            if bearer_token:
                headers["Authorization"] = f"Bearer {bearer_token}"
            elif api_key:
                headers["Authorization"] = f"Bearer {api_key}"

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items = (
                        data.get("data", [])
                        if isinstance(data, dict)
                        else (data if isinstance(data, list) else [])
                    )
                    logger.info(f"BYOK API returned {len(items)} models")
                    return [
                        item["id"]
                        for item in items
                        if isinstance(item, dict) and "id" in item
                    ]
                else:
                    logger.error(f"BYOK API status {resp.status}")
                    return []
    except Exception as e:
        logger.error(f"BYOK API failed: {e}")
        return []


# ── 3. Format & sort ─────────────────────────────────────────────────────────
def format_byok(mid: str) -> Dict:
    return {
        "id": mid,
        "name": f"-{mid}",
        "multiplier": 0.0,
        "raw_id": mid,
        "source": "byok",
        "provider": infer_provider(mid),  # ← infer from ID, not BYOK_TYPE
    }


def sort_and_separate(standard: List[Dict], byok: List[Dict]) -> List[Dict]:
    all_models = standard + byok
    all_models.sort(
        key=lambda x: (
            0 if x.get("source") == "copilot" else 1,
            PROVIDER_ORDER.get(x.get("provider", "unknown"), 3),
            0.0 if x.get("multiplier") is None else x.get("multiplier", 1.0),
            x.get("raw_id", ""),
        )
    )

    if byok and standard:
        sep_idx = next(
            (i for i, m in enumerate(all_models) if m.get("source") == "byok"), None
        )
        if sep_idx:
            all_models.insert(
                sep_idx,
                {
                    "id": "__sep__",
                    "name": "───── BYOK ─────",
                    "source": "separator",
                    "provider": "separator",
                    "raw_id": "__sep__",
                },
            )
    return all_models


# ── Main ─────────────────────────────────────────────────────────────────────
async def main():
    print("=" * 70)
    print("GitHub Copilot SDK — Real API Sort Test")
    print("=" * 70)
    print(f"\n📋 Config:")
    print(f"  GH_TOKEN       : {'***' if GH_TOKEN else '(empty)'}")
    print(f"  BYOK_BASE_URL : {BYOK_BASE_URL or '(empty)'}")
    print(f"  BYOK_TYPE     : {BYOK_TYPE or '(empty)'}")
    print(f"  BYOK_MODELS   : {BYOK_MODELS or '(empty)'}")
    try:
        __import__("copilot")
        copilot_status = "installed"
    except ImportError:
        copilot_status = "NOT installed"
    print(f"  Copilot SDK   : {copilot_status}")

    copilot_models = await fetch_copilot(GH_TOKEN)
    print(f"\n🤖 Copilot models: {len(copilot_models)}")
    if copilot_models:
        logger.info(
            f"  Providers: {dict(Counter(m['provider'] for m in copilot_models))}"
        )

    byok_raw = await fetch_byok(
        BYOK_BASE_URL, BYOK_TYPE, BYOK_API_KEY, BYOK_BEARER_TOKEN
    )
    if not byok_raw and BYOK_MODELS.strip():
        byok_raw = [m.strip() for m in BYOK_MODELS.split(",") if m.strip()]
    print(f"🔑 BYOK models  : {len(byok_raw)}")
    byok_models = [format_byok(m) for m in byok_raw]
    if byok_models:
        logger.info(f"  Providers: {dict(Counter(m['provider'] for m in byok_models))}")

    all_models = sort_and_separate(copilot_models, byok_models)

    print("\n" + "=" * 70)
    print("✅ Final Sorted Model List:")
    print("=" * 70)
    for m in all_models:
        if m.get("source") == "separator":
            print(f"\n  {m['name']}\n")
        else:
            mult = m.get("multiplier", 1.0)
            mult_str = f"{mult:.1f}x" if mult > 0 else "0x"
            print(
                f"  [{m.get('source',''):8}] [{m.get('provider','?'):10}] {mult_str:6}  {m['name']}"
            )

    print("\n🔍 Verification:")
    sep = any(m.get("source") == "separator" for m in all_models)
    c_first = all_models and all_models[0].get("source") == "copilot"
    print(f"  Separator inserted : {'✅' if sep else '❌'}")
    print(f"  Copilot first      : {'✅' if c_first else '❌ (no copilot models)'}")
    print(f"  Copilot models     : {len(copilot_models)}")
    print(f"  BYOK models        : {len(byok_models)}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
