"""
title: Metadata ID Debug
author: Fu-Jie
description: Minimal inlet filter that prints all ID-related fields from __metadata__ to the OpenWebUI server console. Use to verify which IDs OpenWebUI actually sends to filters (chat_id, message_id, user_message_id, assistant_message_id, etc.).
version: 0.1.0
license: MIT
"""

from typing import Optional


class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=0,
            description="Filter priority. Lower runs first. Set above the compression filter's priority so this prints BEFORE compression runs.",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def inlet(
        self,
        body: dict,
        __metadata__: Optional[dict] = None,
    ) -> dict:
        # ── Print everything OpenWebUI puts in __metadata__ ──────────────
        # This is the EXACT object OpenWebUI uses at middleware.py L2357-2361
        # to build the inlet body (chat_id + user_message_id).
        print("\n" + "=" * 72)
        print("[metadata-id-debug] INLET __metadata__ keys:")
        print("=" * 72)
        if not isinstance(__metadata__, dict):
            print(f"  __metadata__ is not a dict: {type(__metadata__).__name__} = {__metadata__!r}")
        else:
            for key in sorted(__metadata__.keys()):
                value = __metadata__[key]
                # Truncate long values (e.g. session_id, tool_ids list)
                value_str = repr(value)
                if len(value_str) > 120:
                    value_str = value_str[:117] + "..."
                print(f"  {key} = {value_str}")

        # ── Highlight the IDs the compression fix depends on ──────────────
        print("-" * 72)
        print("[metadata-id-debug] ID fields of interest:")
        print("-" * 72)
        if isinstance(__metadata__, dict):
            for field in (
                "chat_id",
                "message_id",
                "user_message_id",      # ← the anchor the v1.7.3 fix uses
                "assistant_message_id", # ← used by OpenWebUI's continue path
            ):
                present = field in __metadata__
                value = __metadata__.get(field)
                marker = "PRESENT" if present else "ABSENT "
                print(f"  [{marker}] {field:24} = {value!r}")
        else:
            print("  __metadata__ missing or not a dict")

        # ── Also dump body.metadata (frontend-supplied) for comparison ───
        body_meta = body.get("metadata") if isinstance(body, dict) else None
        print("-" * 72)
        print("[metadata-id-debug] body.metadata (frontend-supplied):")
        print("-" * 72)
        if isinstance(body_meta, dict):
            for key in sorted(body_meta.keys()):
                value_str = repr(body_meta[key])
                if len(value_str) > 120:
                    value_str = value_str[:117] + "..."
                print(f"  {key} = {value_str}")
        else:
            print(f"  body.metadata is not a dict: {type(body_meta).__name__}")

        # ── Message count + branch tip info ──────────────────────────────
        messages = body.get("messages") if isinstance(body, dict) else None
        if isinstance(messages, list):
            print("-" * 72)
            print(f"[metadata-id-debug] body.messages count = {len(messages)}")
            last = messages[-1] if messages else None
            if isinstance(last, dict):
                print(
                    f"  last message: role={last.get('role')!r} "
                    f"id={last.get('id')!r} has_output={'output' in last}"
                )

        print("=" * 72 + "\n")
        return body

    async def outlet(
        self,
        body: dict,
        __metadata__: Optional[dict] = None,
    ) -> dict:
        # Outlet is also called with the same metadata shape; print it too
        # so we can compare inlet vs outlet metadata.
        print("\n" + "=" * 72)
        print("[metadata-id-debug] OUTLET __metadata__ keys:")
        print("=" * 72)
        if isinstance(__metadata__, dict):
            for key in sorted(__metadata__.keys()):
                value_str = repr(__metadata__[key])
                if len(value_str) > 120:
                    value_str = value_str[:117] + "..."
                print(f"  {key} = {value_str}")
        else:
            print(f"  __metadata__ is not a dict: {type(__metadata__).__name__}")
        print("-" * 72)
        if isinstance(__metadata__, dict):
            for field in ("chat_id", "message_id", "user_message_id", "assistant_message_id"):
                present = field in __metadata__
                value = __metadata__.get(field)
                marker = "PRESENT" if present else "ABSENT "
                print(f"  [{marker}] {field:24} = {value!r}")
        print("=" * 72 + "\n")
        return body
