# Code Review Results

**Scope:** extensions `681e0a6..c164226` plus follow-up referenced-summary fix
**Intent:** Prevent injected ACC summaries, including referenced-chat summaries, from acting like current instructions.
**Mode:** extension portion of combined review
**Status:** blocking findings addressed

**Reviewers:** kieran-python, maintainability

### P1 -- High

| # | File | Issue | Reviewer(s) | Confidence | Route |
| --- | --- | --- | --- | --- | --- |
| 1 | `plugins/filters/async-context-compression/async_context_compression.py:3467` | Referenced-chat summary injection bypassed the new sanitizer and safety guard. `_build_summary_message()` stripped `<next_reply_guidance>` and added historical-context framing for normal summary injection, but cached referenced summaries, partial summaries, and generated referenced summaries were wrapped through referenced-chat builders before `__external_references__` injection. That left stale next-reply guidance from a referenced chat model-visible as active-looking context. | kieran-python | 0.90 | `addressed` |

### P3 -- Low

| # | File | Issue | Reviewer(s) | Confidence | Route |
| --- | --- | --- | --- | --- | --- |
| 1 | `plugins/filters/async-context-compression/async_context_compression.py:555` | Summary safety wording now exists both in localized en/zh prefixes and in centralized `SUMMARY_INJECTION_SAFETY_GUARD`. This is behaviorally acceptable but creates two places to keep in sync. Prefer one source of truth for the safety policy in a later cleanup. | maintainability | 0.84 | `advisory -> human` |

### Testing Gaps

| # | File | Gap | Reviewer(s) | Route |
| --- | --- | --- | --- | --- |
| 1 | `plugins/filters/async-context-compression/test_async_context_compression.py:493` | New tests covered `_build_summary_message()` directly, but not referenced-chat `__external_references__` builders. Cached full-summary, partial-summary-plus-tail, and generated referenced-summary cases containing `<next_reply_guidance>` needed coverage. | kieran-python | `addressed` |

### Resolution

- Added `_build_referenced_summary_content()` so referenced cached, partial, and generated summaries also run through `_prepare_summary_for_injection()`.
- Added the same historical/non-instruction safety guard to referenced summary wrappers.
- Left raw referenced-chat direct fallback content as plain escaped content, so non-summary chat text is not mislabeled as a summary.
- Added tests for cached referenced summaries, mixed partial summary plus tail, and generated referenced summaries containing `<next_reply_guidance>`.

### Verification

- `/Users/nex/orca/workspaces/open-webui/Nautilus/.venv/bin/python -m unittest plugins/filters/async-context-compression/test_async_context_compression.py` -> 126 tests OK
- `git diff --check` -> clean

---

> **Verdict:** Ready with one advisory.
>
> **Reasoning:** The referenced-chat summary bypass is fixed and covered. The remaining P3 is a non-blocking source-of-truth cleanup for duplicated summary safety wording.
