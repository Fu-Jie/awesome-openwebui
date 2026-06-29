"""Diagnostic script: trace _load_applicable_summary_snapshot step by step."""
import asyncio
import json
import sys
sys.path.insert(0, ".")
from test_issue98_e2e import (
    Filter, _build_reasoning_chat_openai_compatible,
    _live_refs_by_id, _snapshot,
)

filter_obj = Filter()
filter_obj.valves.keep_last = 0
filter_obj._get_model_thresholds = lambda m: {"max_context_tokens": 100000, "compression_threshold_tokens": 1000}

db_messages, body_messages = _build_reasoning_chat_openai_compatible()
snapshots = [_snapshot("test summary", filter_obj._message_refs_for_prefix(db_messages, 2))]

print("=== Step 0: Data ===")
print(f"db_messages count: {len(db_messages)}")
print(f"body_messages count: {len(body_messages)}")
print(f"snapshot refs: {json.loads(snapshots[0]['covered_message_refs_json'])}")

print("\n=== Step 1: _current_branch_refs(body_messages) ===")
body_refs = filter_obj._current_branch_refs(body_messages)
print(f"body_refs: {body_refs}")

print("\n=== Step 2: _current_branch_refs(db_messages) ===")
db_refs = filter_obj._current_branch_refs(db_messages)
print(f"db_refs: {db_refs}")

print("\n=== Step 3: _compatible_db_branch_for_body_ref_fallback(body, db) ===")
result = filter_obj._compatible_db_branch_for_body_ref_fallback(body_messages, db_messages)
print(f"result: compatible={result[0] is not None}, boundaries={result[1]}, ignored={result[2]}")
if result[1]:
    print(f"  boundaries detail: {result[1]}")

print("\n=== Step 4: _select_applicable_summary_snapshot(snapshots, db_messages) ===")
live_refs = _live_refs_by_id(filter_obj, db_messages)
print(f"live_refs keys: {list(live_refs.keys()) if live_refs else None}")
selected = filter_obj._select_applicable_summary_snapshot(
    snapshots, db_messages, live_message_refs_by_id=live_refs,
)
print(f"selected: {selected}")
if selected is None:
    # Try with debug_mode on to see rejection reason
    filter_obj.valves.debug_mode = True
    selected2 = filter_obj._select_applicable_summary_snapshot(
        snapshots, db_messages, live_message_refs_by_id=live_refs,
    )
    print(f"selected (debug): {selected2}")
    filter_obj.valves.debug_mode = False

print("\n=== Step 5: _message_refs_for_prefix(db_messages, 2) ===")
refs_prefix = filter_obj._message_refs_for_prefix(db_messages, 2)
print(f"refs_prefix: {refs_prefix}")

print("\n=== Step 6: _message_ref for each db_message ===")
for i, msg in enumerate(db_messages):
    ref = filter_obj._message_ref(msg)
    print(f"  db_message[{i}]: id={msg.get('id')}, ref={ref}")
