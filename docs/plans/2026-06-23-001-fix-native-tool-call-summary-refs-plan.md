---
title: fix: Preserve Native Tool-Call Summary Refs
type: fix
status: completed
date: 2026-06-23
origin: docs/development/async-context-compression-branch-aware-summary-review-2-opus-4.8.zh.md
---

# fix: Preserve Native Tool-Call Summary Refs

## Overview

Fix review-2 P1 #1 for the async context compression filter: native tool-calling chats must be able to save and later select branch-valid summary snapshots even when the summary prompt uses unfolded assistant/tool messages. The repair separates canonical OpenWebUI history identity from the prompt-only unfolded representation, so snapshot refs stay aligned with folded history graph message ids instead of synthetic tool-child messages.

## Problem Frame

The current native outlet path unfolds compact assistant `output` into assistant/tool/assistant prompt messages. Those unfolded messages can be id-less, so `_message_refs_for_prefix()` fail-closes and `_generate_summary_async()` saves only the legacy `chat_summary` row, not a branch-valid `chat_summary_snapshot`. Inlet still validates against folded request messages with real OpenWebUI ids, so even a saved snapshot from unfolded refs would not match the current branch safely.

The fix must not invent synthetic ids for unfolded children. Branch safety depends on real history graph identity: live sibling refs must reject, deleted refs may be skipped only when the full graph proves absence, and edited folded messages must invalidate via fingerprint.

## Requirements Trace

- R1. Native tool-calling chats whose assistant messages contain `output` can generate branch-valid snapshots.
- R2. Snapshot `covered_message_refs`, `compressed_message_count`, `source_current_id`, and selection inputs use folded OpenWebUI history refs, not id-less unfolded prompt messages.
- R3. Summary generation can still see native tool-call details by formatting an unfolded prompt view when useful.
- R4. Coverage never claims a folded live-tail message unless the prompt slice included that folded message's complete unfolded representation; folded refs already represented by a validated summary marker may be carried forward through the existing marker-overlap contract.
- R5. Existing branch safety invariants remain fail-closed: live siblings reject, deleted refs require full-graph proof, stale fingerprints reject, and atomic tool groups cannot be cut.
- R6. Existing non-native and legacy summary behavior remains compatible.

## Scope Boundaries

- Do not introduce DB schema changes or new snapshot retention policy.
- Do not synthesize stable ids for assistant/tool child messages created by `convert_output_to_messages(raw=True)`.
- Do not reopen review-2 issues #2 and #3, which are already handled by the previous commit.
- Do not change the user-visible summary prompt contract except as needed to include native tool-call details safely.

## Context & Research

### Relevant Code and Patterns

- `plugins/filters/async-context-compression/async_context_compression.py`
  - `_unfold_messages()` expands assistant `output` into id-less prompt messages.
  - `_message_ref()` and `_message_refs_for_prefix()` require stable folded message ids.
  - `_select_applicable_summary_snapshot()` already validates branch refs and rejects atomic-boundary splits.
  - `_reconstruct_active_history_branch()` already uses `history.messages` map keys as canonical ids when embedded ids are missing.
  - `outlet()` currently chooses DB/body source and unfolds it before target calculation and summary generation.
  - `_generate_summary_async()` currently uses a single `messages` list for prompt slicing, coverage count, covered refs, and source current id.
- `plugins/filters/async-context-compression/test_async_context_compression.py`
  - Existing tests cover sibling/deleted discrimination, nearest ancestor selection, image fingerprints, atomic group rejection, and summary save paths.

### Institutional Learnings

- `docs/solutions/workflow-issues/centralize-scoped-base-model-identity-2026-05-14.md`: keep storage identity and runtime-facing identity separate, centralize helper boundaries, and test both sides. Applied here as canonical folded refs vs prompt-only unfolded messages.

### External References

- None. The bug is specific to local OpenWebUI history shape and the plugin's snapshot identity contract.

## Key Technical Decisions

- Canonical refs are folded history refs. Snapshot persistence and selection must use real OpenWebUI message ids from folded body or DB history, with history map keys filling missing embedded ids.
- Unfolded native messages are prompt-only. They may improve summary content, but they cannot define snapshot identity or branch membership.
- Use an explicit side-car mapping or equivalent source-boundary contract between folded messages and unfolded prompt messages. The implementation may choose the smallest local abstraction, but the boundary must make it impossible to compute refs from id-less unfolded children.
- Prefer DB active-branch history as the native outlet canonical source only when it is branch-equivalent to the request body, at least as complete, and has matching folded refs/fingerprints for the body overlap. Fall back to body messages only when they expose stable folded refs; otherwise fail closed to compatibility summary.
- Fail closed when canonical folded refs cannot be reconstructed. Compatibility `chat_summary` saving may continue, but branch-valid snapshot save/reuse must not proceed.
- Treat prompt-only transient dependencies as non-reusable. If the fitted summary prompt includes external references, pending inlet restorations, or other content that cannot be represented by canonical folded refs or a validated summary marker, save only compatibility `chat_summary` rather than a branch-valid snapshot.

## Open Questions

### Resolved During Planning

- Should unfolded children receive synthetic ids? No. Synthetic child ids are not in the OpenWebUI history graph and would break sibling/deleted safety.
- Should native summary prompt lose tool details to keep folded refs simple? No. Keep prompt detail by unfolding for summary text, but map coverage back to folded refs.
- Which representation should inlet selection use? Folded current-branch messages, as it already does.
- How should DB/body divergence be handled? DB folded history may define canonical refs only when its active branch is branch-equivalent to the body overlap and fingerprint-compatible; loose length checks are insufficient.
- Can prompt-only transient content be persisted in branch-valid snapshots? No. Without canonical refs, that content is not validated on reuse, so it must downgrade the save to compatibility summary only.

### Deferred to Implementation

- Exact helper naming and field names for the folded-to-prompt mapping are deferred, but the carrier/API shape is not: the async summary boundary must receive a source object or equivalent structured payload containing both prompt messages and canonical folded messages/coverage refs. It must not pass a single ambiguous `messages` list as both prompt view and identity source.
- Exact prompt formatting for folded assistant `output`: if unfolding cannot be made safe in a narrow patch, folded messages may be formatted with output-derived text instead, as long as tests prove tool output appears in the summary input and refs remain folded.

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

```text
OpenWebUI folded history branch
  -> canonical refs, target count, source_current_id, snapshot selection
  -> native prompt view, possibly unfolded assistant/tool messages
       -> summary LLM input only
  -> save snapshot using canonical covered refs for the folded coverage boundary
```

The important invariant is that coverage flows from folded source to prompt view and back to folded refs. The unfolded prompt view must never become the authoritative message identity source.

## Implementation Units

- [x] **Unit 1: Introduce Canonical Native Summary Source**

**Goal:** Represent native outlet summary input as separate canonical folded messages and prompt messages.

**Requirements:** R1, R2, R3, R6

**Dependencies:** None

**Files:**
- Modify: `plugins/filters/async-context-compression/async_context_compression.py`
- Test: `plugins/filters/async-context-compression/test_async_context_compression.py`

**Approach:**
- Add a small internal boundary for summary sources that keeps folded messages available after native unfolding.
- Ensure native outlet chooses the canonical folded source before unfolding, using DB active-branch history only when it is branch-equivalent to the request body overlap and fingerprint-compatible.
- Create or modify the canonical-source loader so it prefers `history.messages` + `currentId` for folded refs when that graph is present, applies map-key ids before ref validation, and uses top-level direct messages only as a prompt/body fallback or when they independently expose stable folded refs.
- Preserve existing summary marker reinjection semantics, but apply them in a way that does not lose the folded ref source.
- Keep external reference and transient pending messages out of canonical refs unless they are validated summary markers; if they remain in the prompt slice, branch-valid snapshot save must fail closed.

**Execution note:** Add characterization coverage for an id-less unfolded native `output` expansion before changing the save path.

**Patterns to follow:**
- `_reconstruct_active_history_branch()` for using history map keys as stable ids.
- Existing `_build_summary_progress_snapshot()` debug output style for source diagnostics.

**Test scenarios:**
- Happy path: a folded assistant message with `id` and `output` expands into id-less tool messages, but the source object still exposes folded refs for the assistant id.
- Edge case: DB history is available and body messages are shorter; canonical refs come from DB folded messages while prompt messages may unfold.
- Edge case: DB history is longer but branch/fingerprint overlap does not match the body; branch-valid snapshot save falls back to body stable refs or compatibility summary rather than mixing sources.
- Edge case: body fallback is used only when folded body messages provide stable refs.
- Error path: prompt-only transient content is present in the fitted summary prompt without canonical refs; compatibility summary can save, but `covered_message_refs` is omitted.

**Verification:**
- Native source selection can produce prompt messages for summary generation and canonical refs for snapshot persistence without relying on synthetic child ids.

- [x] **Unit 2: Save Native Snapshots in Folded Coordinates**

**Goal:** Update summary generation so `compressed_message_count`, `covered_message_refs`, `source_current_id`, and protected-head metadata come from canonical folded coverage.

**Requirements:** R1, R2, R4, R5

**Dependencies:** Unit 1

**Files:**
- Modify: `plugins/filters/async-context-compression/async_context_compression.py`
- Test: `plugins/filters/async-context-compression/test_async_context_compression.py`

**Approach:**
- Make `_generate_summary_async()` or its caller accept canonical coverage input separately from the prompt message list.
- Pass a structured source payload across the async boundary so prompt messages and canonical folded refs cannot be accidentally recombined as one list.
- Continue fitting and formatting the prompt view for the summary LLM.
- When prompt fitting removes newer messages, translate the fitted prompt boundary back to a folded coverage boundary and save refs only through that boundary.
- If the prompt boundary cannot be mapped to complete folded messages, reduce coverage to the last complete folded message or fail closed to compatibility summary only.
- Derive `source_current_id` from canonical current-branch refs.

**Patterns to follow:**
- `_message_refs_for_prefix()` marker-overlap handling for trusted summary markers.
- `_align_tail_start_to_atomic_boundary()` and `_get_atomic_groups()` for not cutting native tool-call groups.

**Test scenarios:**
- Happy path: `_generate_summary_async()` on native folded messages with id-less unfolded prompt children captures `covered_message_refs` for folded ids and a non-empty `source_current_id`.
- Happy path: the summary LLM input includes the tool output text from the unfolded prompt view.
- Edge case: prompt fitting removes a native unfolded block; saved coverage does not claim the folded source message for the removed block.
- Error path: no stable canonical refs are available; only compatibility summary is saved and branch-valid snapshot metadata is omitted.

**Verification:**
- A native tool-call conversation that crosses the compression threshold writes a `chat_summary_snapshot` with folded ids, not id-less prompt children.

- [x] **Unit 3: Preserve Folded Selection and Reinjection Semantics**

**Goal:** Ensure inlet and outlet select and reinject snapshots against folded current-branch messages while summary prompt construction remains independent.

**Requirements:** R2, R5, R6

**Dependencies:** Units 1 and 2

**Files:**
- Modify: `plugins/filters/async-context-compression/async_context_compression.py`
- Test: `plugins/filters/async-context-compression/test_async_context_compression.py`

**Approach:**
- Keep `_load_applicable_summary_snapshot()` and `_select_applicable_summary_snapshot()` on canonical folded messages.
- In outlet, call selection/reinjection with folded source messages rather than unfolded prompt messages.
- When a previous summary is injected for successor compression, ensure the marker's covered refs are folded refs and the new live tail is mapped consistently into the prompt view.
- Preserve fail-closed behavior when full graph refs are unavailable for unmatched refs.

**Patterns to follow:**
- Existing tests `test_inlet_uses_only_latest_matching_snapshot_for_current_branch`, `test_snapshot_selection_discriminates_deleted_vs_sibling`, and `test_snapshot_selection_rejects_coverage_that_splits_tool_group`.

**Test scenarios:**
- Integration: save a native tool-call snapshot using folded refs, then select it through the folded inlet view and inject exactly one summary marker plus live tail.
- Error path: a native snapshot from a sibling branch is rejected when its folded id remains live in the full history graph.
- Edge case: a deleted folded ref can be skipped only when the full graph refs prove it is absent.

**Verification:**
- Current branch requests use the latest valid folded snapshot and never reuse a native snapshot solely because unfolded prompt text matches.

- [x] **Unit 4: Update Review Tracking and Regression Coverage**

**Goal:** Mark review-2 #1 as addressed with concrete verification and keep future regressions visible.

**Requirements:** R1, R5, R6

**Dependencies:** Units 1-3

**Files:**
- Modify: `docs/development/async-context-compression-branch-aware-summary-review-2-opus-4.8.zh.md`
- Modify: `plugins/filters/async-context-compression/test_async_context_compression.py`

**Approach:**
- Add or update targeted regression tests for the exact review failure: id-less unfolded native output no longer prevents branch-valid snapshot save or folded inlet selection.
- Update the review document's #1 status from deferred to addressed once implementation and targeted tests pass.
- Keep unrelated open review items unchanged.

**Patterns to follow:**
- Existing review status tables in `docs/development/async-context-compression-branch-aware-summary-review-2-opus-4.8.zh.md`.

**Test scenarios:**
- Integration: native tool-call chain saves snapshot, reloads/selects snapshot, and rejects sibling/edit cases through folded refs.
- Regression: no synthetic unfolded child ids appear in saved covered refs.

**Verification:**
- The review document records the fix and the targeted test result for #1 only.

## System-Wide Impact

- **Interaction graph:** Touches inlet snapshot selection, outlet source selection, background summary generation, and summary persistence.
- **Error propagation:** Missing canonical refs should continue to warn and save compatibility summary only; it must not inject unsafe branch snapshots.
- **State lifecycle risks:** DB/body divergence can cause snapshots that never match inlet if refs are taken from the wrong source. Canonical source selection must be explicit.
- **API surface parity:** No public API, valve, schema, or README contract change is expected.
- **Integration coverage:** Unit tests must exercise outlet save plus folded inlet selection, not only helper-level ref generation.
- **Unchanged invariants:** Retain-all snapshot policy, 80/20 summary valve validation, protected-head handling, previous-summary no-trim behavior, and atomic group rejection remain in force.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Prompt and folded coverage boundaries drift | Keep an explicit mapping/coverage contract and test prompt trimming scenarios. |
| Synthetic ids accidentally enter persisted refs | Assert saved refs are folded ids and contain no tool-child placeholder ids. |
| DB history differs from body messages | Require branch-equivalent, fingerprint-compatible overlap before using DB as canonical source; otherwise fall back to body with stable refs or fail closed. |
| Prompt-only transient content is summarized into reusable snapshots | Downgrade branch-valid snapshot save to compatibility summary whenever fitted prompt content lacks canonical folded refs or validated marker metadata. |
| Fix over-refactors the already complex summary path | Keep changes local to source selection, mapping, and save/selection boundaries; avoid unrelated cleanup. |

## Documentation / Operational Notes

- Update the review document to close #1 after code and tests pass.
- README plugin introduction does not need a user-facing update unless implementation changes valves or external behavior; this plan expects no README change.

## Sources & References

- Origin document: `docs/development/async-context-compression-branch-aware-summary-review-2-opus-4.8.zh.md`
- Related code: `plugins/filters/async-context-compression/async_context_compression.py`
- Related tests: `plugins/filters/async-context-compression/test_async_context_compression.py`
- Institutional learning: `docs/solutions/workflow-issues/centralize-scoped-base-model-identity-2026-05-14.md`
