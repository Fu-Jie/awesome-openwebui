---
title: feat: Branch-Aware Compression Test Harness
type: feat
status: active
date: 2026-06-24
---

# feat: Branch-Aware Compression Test Harness

## Overview

Add a reusable, generated test harness for the async context compression filter's branch-aware summary behavior. The harness should model OpenWebUI conversation history as a tree, generate realistic branch/delete/edit/interleaving scenarios, mock only the summary LLM output, and verify the plugin's selection, derivation, persistence, and injection logic through executable tests.

## Problem Frame

Branch-aware compression is now a persistent-data feature with non-trivial tree semantics. Existing tests cover many focused helper and regression cases, but they are mostly hand-authored single examples. The larger risk is not one helper failing in isolation; it is that combinations of summaries, branch forks, deleted messages, edited payloads, alternating active branches, and repeated compression boundaries drift from the intended invariant:

- multiple branch-valid summaries may coexist;
- only the newest summary valid for the current branch may be injected;
- new compression should derive from the nearest valid ancestor summary plus live tail messages;
- live sibling refs must reject stale summaries;
- deleted refs may be tolerated only when absent from the full history graph;
- summary LLM content is irrelevant for these tests and should be mocked.

## Requirements Trace

- R1. Build a reusable test data model that can generate OpenWebUI-like message trees with stable message ids, parent relationships, active branch views, edits, deletes, and sibling branches.
- R2. Exercise repeated compression derivation across multiple saved summaries, including non-aligned fork points such as summaries for `1-5` and `1-10` with a branch from `7`.
- R3. Verify alternating active branches: continuing one branch should not reuse another branch's newer summary, and returning to the other branch should reuse its own newest valid summary.
- R4. Verify deleted-message behavior: refs missing from the current branch may be skipped only when the generated full graph proves the message is deleted, not merely off-chain.
- R5. Verify edited payload behavior: same ids with changed content or attachments invalidate stale summaries by fingerprint.
- R6. Mock summary LLM output while running the real compression, selection, prompt fitting, save, and injection logic wherever practical.
- R7. Keep tests deterministic and readable: generated datasets should be named and inspectable, not random fuzz that fails opaquely.
- R8. Integrate the new tests into the existing pytest/unittest file or adjacent test module without requiring external services.

## Scope Boundaries

- Do not change production behavior unless tests reveal a real defect.
- Do not call real LLMs or network services.
- Do not add property-based testing dependencies unless the existing environment already includes them; deterministic table/scenario generation is enough.
- Do not move the plugin to a new package layout in this iteration.
- Do not commit unrelated existing changes such as `docs/zh/future_plugin_development_roadmap_cn.md`.

## Context & Research

### Relevant Code and Patterns

- `plugins/filters/async-context-compression/async_context_compression.py`
  - `ChatSummary` stores branch-aware summary rows in `chat_summary`.
  - `_message_ref()`, `_message_refs_for_prefix()`, and `_history_graph_refs_by_id()` define identity and fingerprint behavior.
  - `_select_applicable_summary_snapshot()` chooses the newest branch-valid summary.
  - `inlet()` injects validated summaries and live tail context.
  - `_generate_summary_async()` derives a successor summary from a previous summary marker or DB-loaded summary.
  - `_save_summary()` persists branch-aware coverage refs.
- `plugins/filters/async-context-compression/test_async_context_compression.py`
  - Existing helpers `_messages_with_ids()`, `_snapshot()`, and `_live_refs_by_id()` are useful but too flat for complex branch-tree generation.
  - Existing tests already cover sibling rejection, nearest ancestor selection, deleted vs sibling discrimination, payload fingerprint changes, inlet use of latest matching summary, and previous-summary generation paths.
- `docs/plans/2026-06-23-001-fix-native-tool-call-summary-refs-plan.md`
  - Shows local plan style and confirms the plugin's test strategy favors direct, focused unit/integration coverage in `test_async_context_compression.py`.

### Institutional Learnings

- No `docs/solutions/` directory exists in this repo checkout, so there were no local solution notes to incorporate.

### External References

- None. This is local plugin behavior with repository-specific data shapes.

## Key Technical Decisions

- Use deterministic scenario generation, not random fuzzing. The goal is comprehensive, debuggable coverage over known tree shapes.
- Model branch state independently from plugin internals, then convert to normal OpenWebUI-like message dictionaries and full-graph refs for the plugin. This avoids encoding the plugin's assumptions directly into expected results.
- Mock only `_call_summary_llm()` for summary text. Summary content can be stable labels such as `summary:<scenario>:<covered_ids>`, while all selection, fitting, saving, and injection logic remains real.
- Prefer in-memory fake persistence over a real database unless the current tests already provide an easy DB fixture. The fake should behave like multiple `chat_summary` rows, including row retention and newest-valid selection.
- Keep test assertions semantic: active summary content, covered ids, live tail ids, saved rows, and rejected rows. Avoid brittle assertions on incidental debug log text.

## Open Questions

### Resolved During Planning

- Should tests mock user/assistant inputs too? No. User and assistant messages should be generated as realistic deterministic fixtures; only the summary LLM output is mocked.
- Should scenarios live in a separate file? Start in `test_async_context_compression.py` unless the harness becomes large enough to justify `tests` support files.
- Should this include browser tests? No. The behavior is backend filter logic, not UI. LFG's browser-test step should be recorded as not applicable unless a browser-facing regression is introduced.

### Deferred to Implementation

- Exact helper class names are deferred. The implementation should choose names that fit the existing test style.
- Whether to add a small adjacent test module is deferred; keep all tests discoverable by the existing pytest command either way.

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

```text
Generated branch graph
  -> active branch message list
  -> full live/deleted graph refs
  -> generated saved summary rows
  -> filter.inlet / filter._generate_summary_async / filter._select_applicable_summary_snapshot
  -> assertions over selected summary, live tail, saved coverage, and rejected siblings
```

The generated data should support non-aligned fork examples:

```text
main:    m0 -> m1 -> m2 -> m3 -> m4 -> m5 -> m6 -> m7 -> m8 -> m9
summaries: [m0..m4], [m0..m9]
branchB: m0 -> m1 -> m2 -> m3 -> m4 -> m5 -> m6 -> b7 -> b8
expected on branchB: reuse [m0..m4], keep m5/m6/b7/b8 live, reject [m0..m9]
successor: save [m0..b8] for branchB
```

## Implementation Units

- [x] **Unit 1: Deterministic Branch Scenario Builder**

**Goal:** Add helpers that generate branch-tree message fixtures, active branches, full graph refs, edited messages, deleted messages, and saved summary rows.

**Requirements:** R1, R2, R4, R5, R7

**Dependencies:** None

**Files:**
- Modify: `plugins/filters/async-context-compression/test_async_context_compression.py`

**Approach:**
- Add a compact helper layer near the existing `_messages_with_ids()` and `_snapshot()` helpers.
- Represent generated messages with stable ids and content payloads that can be edited deterministically.
- Provide methods to:
  - create a linear main branch;
  - fork from any existing node;
  - mark a node deleted from the full live graph;
  - edit a node payload while preserving id;
  - return active branch messages;
  - return full graph refs by id for live sibling/deleted discrimination;
  - create summary rows from a branch prefix.
- Keep all generated fixtures explicit enough that failing assertions print useful ids.

**Patterns to follow:**
- Existing `_messages_with_ids()` role assignment and `_snapshot()` shape.
- Existing tests that call `_select_applicable_summary_snapshot()` with `live_message_refs_by_id`.

**Test scenarios:**
- Happy path: generated linear branch produces expected ids and refs.
- Edge case: fork from a point that is not a previous compression boundary.
- Edge case: edited payload keeps id but changes fingerprint.
- Edge case: deleted node is absent from full graph while sibling node remains live.

**Verification:**
- Scenario builder helpers are exercised by at least one direct sanity test or by the first generated scenario test with clear expected ids.

- [x] **Unit 2: Generated Selection and Inlet Scenarios**

**Goal:** Use generated scenarios to prove summary selection and inlet injection across complex branch trees.

**Requirements:** R2, R3, R4, R5, R7

**Dependencies:** Unit 1

**Files:**
- Modify: `plugins/filters/async-context-compression/test_async_context_compression.py`

**Approach:**
- Create a table of named scenarios and run them through `_select_applicable_summary_snapshot()` and `inlet()`.
- Include expected selected summary label, expected covered ids, and expected live tail ids.
- Patch `_load_applicable_summary_snapshot()` to use generated rows and generated full-graph refs, while leaving `inlet()` itself real.

**Test scenarios:**
- Happy path: main branch with summaries `1-5`, `1-10`, `1-15` injects only `1-15`.
- Integration: non-aligned fork from message `7` rejects `1-10`, reuses `1-5`, and keeps `6`, `7`, and sibling messages in live tail.
- Integration: after a sibling branch has its own successor summary, returning to main still injects main's newest valid summary, while branchB injects branchB's newest valid summary.
- Edge case: deleted message inside a saved summary can be skipped when absent from full graph.
- Error path: live sibling message inside a saved summary rejects that summary.
- Error path: edited same-id message rejects stale summary via fingerprint mismatch.

**Verification:**
- Generated inlet tests assert exactly one summary marker is injected, its content label matches the expected row, and all non-covered current-branch messages remain in order.

- [x] **Unit 3: Generated Compression Derivation Scenarios**

**Goal:** Verify repeated compression derives new summaries from the nearest valid ancestor summary plus new branch messages, with summary LLM output mocked.

**Requirements:** R2, R3, R6, R7

**Dependencies:** Units 1 and 2

**Files:**
- Modify: `plugins/filters/async-context-compression/test_async_context_compression.py`

**Approach:**
- Mock `_call_summary_llm()` to return deterministic summary labels.
- Mock `_save_summary()` or use a fake in-memory save collector to capture `summary`, `compressed_count`, and `covered_message_refs`.
- Run `_generate_summary_async()` against active branch views that contain either:
  - an injected summary marker plus live tail; or
  - raw DB messages where `_load_applicable_summary_snapshot()` supplies the previous branch-valid summary.
- Assert the mocked LLM receives the previous summary when expected, the conversation text contains only the intended live-tail messages, and saved coverage matches current-branch refs.

**Test scenarios:**
- Happy path: branchB derives `1-9b` from previous `1-5` plus `6`, `7`, `8b`, `9b`.
- Happy path: main branch later derives `1-12` from previous `1-10` plus `11`, `12`.
- Integration: alternating branches produce two saved rows with different covered refs and neither overwrites the other.
- Edge case: previous summary exists but covers the target boundary already; generation skips rather than saving a duplicate.
- Edge case: oversized summary prompt still keeps the previous summary and at least one new message when possible.

**Verification:**
- Tests prove summary LLM text is mocked, but the plugin's real prompt construction, previous-summary lookup, coverage counting, and save-boundary logic are exercised.

- [x] **Unit 4: Fake Persistence for Multi-Row Summary Storage**

**Goal:** Add a small fake summary store that behaves like multiple branch-aware `chat_summary` rows so end-to-end scenario tests do not need a real database.

**Requirements:** R3, R6, R8

**Dependencies:** Units 1-3

**Files:**
- Modify: `plugins/filters/async-context-compression/test_async_context_compression.py`

**Approach:**
- Build an in-memory store around the same row shape used by `_snapshot()`.
- Provide fake `_load_applicable_summary_snapshot()` and `_save_summary()` bindings for a filter instance.
- Preserve chronological ordering enough to test "newest valid summary" selection.
- Keep deleted/sibling/full-graph refs available to selection.

**Test scenarios:**
- Happy path: store retains summaries for main and branchB simultaneously.
- Happy path: store load returns the newest valid row for the active branch.
- Error path: store load returns no row when all candidates are stale or sibling-invalid.
- Integration: fake save followed by fake load makes the newly derived branch summary available to `inlet()`.

**Verification:**
- End-to-end generated scenarios can alternate active branches using one fake store and assert correct reuse without real DB or LLM calls.

- [x] **Unit 5: Test Organization and Runtime Guardrails**

**Goal:** Keep the expanded coverage maintainable and fast.

**Requirements:** R7, R8

**Dependencies:** Units 1-4

**Files:**
- Modify: `plugins/filters/async-context-compression/test_async_context_compression.py`

**Approach:**
- Use named subtests or separate test methods so failures identify the generated scenario name.
- Avoid global mutable state between scenarios; each test gets a fresh filter and fake store.
- Keep helper output and assertions focused on ids, summary labels, and covered refs.
- Run the existing targeted pytest file and ensure new tests do not require external services.

**Test scenarios:**
- Meta: scenario names appear in subtest failures.
- Meta: fake summary LLM is called only in derivation tests, never in pure selection/inlet tests.
- Meta: generated tests do not depend on wall-clock ordering except controlled row timestamps or insertion order.

**Verification:**
- The full async context compression test file passes locally with the existing pytest command.

## System-Wide Impact

- **Interaction graph:** New tests touch scenario generation, selection helpers, `inlet()`, `_generate_summary_async()`, fake persistence, and mocked summary LLM boundaries.
- **Error propagation:** Tests should prove unsafe summaries are rejected without raising, while valid older summaries can still keep the request usable.
- **State lifecycle risks:** Fake persistence must model multi-row retention closely enough to catch branch alternation regressions.
- **API surface parity:** No user-facing API or valve changes are planned.
- **Integration coverage:** The new tests should cover selection plus inlet injection plus successor compression save/load, not only pure helper selection.
- **Unchanged invariants:** Summary content remains unimportant for logic tests; the mocked summary string should not affect branch validity.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Generated harness duplicates plugin logic and creates false confidence | Keep builder independent: it creates tree fixtures and expected ids, while plugin functions compute refs and selection. |
| Tests become too abstract to debug | Use deterministic named scenarios, explicit expected ids, and subtests. |
| Fake store drifts from `chat_summary` behavior | Reuse `_snapshot()` row shape and `_select_applicable_summary_snapshot()` for loading semantics. |
| Coverage misses async derivation path | Include `_generate_summary_async()` tests with mocked `_call_summary_llm()` and captured `_save_summary()`. |
| Expanded tests are slow | Avoid real DB, network, browser, and real LLM calls. |

## Documentation / Operational Notes

- No user-facing documentation is required for this test-only change.
- If implementation reveals a production bug, document that fix in the final summary and add focused regression coverage alongside generated scenario coverage.

## Sources & References

- Related code: `plugins/filters/async-context-compression/async_context_compression.py`
- Existing tests: `plugins/filters/async-context-compression/test_async_context_compression.py`
- Prior plan style: `docs/plans/2026-06-23-001-fix-native-tool-call-summary-refs-plan.md`
