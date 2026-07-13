"""
title: Metadata ID Debug
author: Fu-Jie
description: Minimal inlet/outlet filter that prints all ID-related fields from __metadata__ to the BROWSER console (DevTools) via __event_emitter__ execute events. Use to verify which IDs OpenWebUI actually sends to filters (chat_id, message_id, user_message_id, assistant_message_id, etc.).
version: 0.2.0
license: MIT
"""

import json
from typing import Any, Awaitable, Callable, Optional

from pydantic import BaseModel, Field


class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=0,
            description="Filter priority. Set LOWER than the compression filter so this runs first and prints the raw metadata.",
        )

    def __init__(self):
        self.valves = self.Valves()

    # ── Browser console emitter (same pattern as folder-memory plugin) ──
    # OpenWebUI frontend executes the JS in data.code; console.log then
    # appears in the browser DevTools Console (F12).
    async def _console_log(
        self,
        __event_emitter__: Optional[Callable[[Any], Awaitable[None]]],
        label: str,
        payload: Any,
    ) -> None:
        if not __event_emitter__:
            return
        try:
            # JSON-serialize the payload so it survives embedding in JS.
            # ensure_ascii=False keeps non-ASCII readable in the console.
            json_str = json.dumps(payload, ensure_ascii=False, default=str)
            js_code = f'console.log("[metadata-id-debug] {label}", {json_str});'
            await __event_emitter__(
                {"type": "execute", "data": {"code": js_code}}
            )
        except Exception as exc:
            # Fall back silently — this is a debug filter, never break the chat.
            print(f"[metadata-id-debug] emit failed: {exc}")

    def _summarize_metadata(self, __metadata__: Any) -> dict:
        """Build a compact dict of the metadata fields we care about."""
        if not isinstance(__metadata__, dict):
            return {"_error": f"__metadata__ is not a dict: {type(__metadata__).__name__}"}

        # All keys (sorted) so we can see the full shape OpenWebUI sends.
        all_keys = sorted(__metadata__.keys())

        # ID fields the v1.7.3 branch-divergence fix depends on.
        ids = {}
        for field in (
            "chat_id",
            "message_id",
            "user_message_id",       # ← the anchor the v1.7.3 fix uses
            "assistant_message_id",  # ← used by OpenWebUI's continue path
        ):
            ids[field] = {
                "present": field in __metadata__,
                "value": __metadata__.get(field),
            }

        return {"all_keys": all_keys, "ids_of_interest": ids}

    def _summarize_body(self, body: dict) -> dict:
        """Compact body summary (avoid dumping the whole messages array)."""
        if not isinstance(body, dict):
            return {"_error": f"body is not a dict: {type(body).__name__}"}

        messages = body.get("messages")
        last = None
        if isinstance(messages, list) and messages:
            last_msg = messages[-1]
            if isinstance(last_msg, dict):
                last = {
                    "role": last_msg.get("role"),
                    "id": last_msg.get("id"),
                    "has_output": "output" in last_msg,
                }

        body_meta = body.get("metadata")
        body_meta_keys = sorted(body_meta.keys()) if isinstance(body_meta, dict) else None

        return {
            "message_count": len(messages) if isinstance(messages, list) else None,
            "last_message": last,
            "body_metadata_keys": body_meta_keys,
        }

    async def inlet(
        self,
        body: dict,
        __metadata__: Optional[dict] = None,
        __event_emitter__: Optional[Callable[[Any], Awaitable[None]]] = None,
    ) -> dict:
        # ── Emit to browser console (DevTools → Console) ──────────────────
        await self._console_log(
            __event_emitter__,
            "INLET __metadata__",
            self._summarize_metadata(__metadata__),
        )
        await self._console_log(
            __event_emitter__,
            "INLET body summary",
            self._summarize_body(body),
        )
        return body

    async def outlet(
        self,
        body: dict,
        __metadata__: Optional[dict] = None,
        __event_emitter__: Optional[Callable[[Any], Awaitable[None]]] = None,
    ) -> dict:
        # Outlet is called with the same metadata shape; emit it too so we
        # can compare inlet vs outlet metadata (e.g. whether assistant_message_id
        # appears only at outlet time).
        await self._console_log(
            __event_emitter__,
            "OUTLET __metadata__",
            self._summarize_metadata(__metadata__),
        )
        await self._console_log(
            __event_emitter__,
            "OUTLET body summary",
            self._summarize_body(body),
        )
        return body
