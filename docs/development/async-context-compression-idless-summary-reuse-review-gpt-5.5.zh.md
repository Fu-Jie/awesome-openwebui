---
title: "代码评审：Async Context Compression idless request summary reuse"
type: review
status: addressed
date: 2026-06-26
target_commit: 07d26c1a1e641f6b79f20d199e8b807c27d048ee
target: plugins/filters/async-context-compression
reviewer: gpt-5.5
---

# 代码评审：Async Context Compression idless request summary reuse

## Code Review Results

**Scope:** `extensions` 子仓库最新提交 `07d26c1 fix(async-context-compression): reuse summaries for idless requests`。

**Intent:** 当 Open WebUI middleware 发给模型的 request body 缺少稳定 message ids，或 DB active branch 比 request body 多一个 terminal assistant placeholder 时，插件先用 DB active branch 证明 body 与当前可见分支一致，再复用已有 branch-aware summary，避免错误退回超长原始历史。

**Mode:** report-only review。主线程复核代码并运行插件测试；并行使用 correctness、testing、maintainability 评审视角。未修改实现代码。

**Reviewers:** correctness、testing、maintainability、主线程复核。

## Addressing Update

2026-06-26 已处理本轮 review 的所有 actionable 项：

- P2 #1: debug 日志路径改为使用当前 snapshot 实际使用的 `current_refs_for_snapshot`，不再在 idless fallback 场景对 `current_refs=None` 切片。新增 `test_snapshot_selection_debug_handles_idless_tail_with_multiple_snapshots` 覆盖 `debug_mode=True + 多 snapshot + idless tail`。
- P2 #2: `_unfold_db_branch_for_body_ref_fallback()` 现在捕获 `convert_output_to_messages()` 的普通异常并 fail closed，拒绝 DB ref fallback，而不是让 inlet 失败。新增 `test_unfold_db_branch_fallback_rejects_conversion_errors`。
- P2 #3: 新增 `test_inlet_reuses_same_length_idless_body_that_omits_db_output`，覆盖同长度 idless body 省略 DB assistant `output` 的正向复用，并断言 tool call mismatch 会拒绝 fallback。
- P2 #4: 新增 `test_load_full_chat_messages_filters_failed_assistant_from_direct_messages`，覆盖 direct `chat["messages"]` 路径的 failed assistant 过滤。
- P3 #5: 新增 `test_unfolded_db_message_allows_trimmed_assistant_only_with_metadata`，覆盖 assistant `metadata.tool_outputs_trimmed` 容忍分支及缺少 metadata 时的负例。

验证：

- `../.venv/bin/python -m pytest plugins/filters/async-context-compression/test_async_context_compression.py -k "idless or output or failed_assistant or tool_outputs_trimmed or conversion_errors or debug"` -> `19 passed, 92 deselected`
- `../.venv/bin/python -m pytest plugins/filters/async-context-compression/test_async_context_compression.py` -> `111 passed`
- `git diff --check` -> passed

## Findings

### P2 -- Moderate

| # | File | Issue | Reviewer(s) | Confidence | Route |
|---|------|-------|-------------|------------|-------|
| 1 | `plugins/filters/async-context-compression/async_context_compression.py:1583` | `_select_applicable_summary_snapshot()` 现在允许 `current_refs is None`，但 debug 日志分支仍执行 `current_refs[:...]`。当 idless body 只能通过 DB prefix 生成 refs、已有 best snapshot、后续低分 snapshot 进入 `debug_mode=True` 日志路径时，会抛 `TypeError`，把本应可选的 debug 诊断变成 inlet 请求失败。 | correctness, maintainability | 0.90 | `safe_auto -> review-fixer`, requires verification |
| 2 | `plugins/filters/async-context-compression/async_context_compression.py:2313` | `_unfold_db_branch_for_body_ref_fallback()` 只捕获 `ImportError`。如果 `convert_output_to_messages()` 因 Open WebUI 版本漂移、异常 `output` payload 或转换 bug 抛出普通异常，DB fallback 不会 fail closed，而是让 inlet 整体失败。该路径是可选兼容 fallback，应拒绝复用而不是中断请求。 | maintainability | 0.78 | `safe_auto -> review-fixer`, requires verification |
| 3 | `plugins/filters/async-context-compression/async_context_compression.py:2203` | 同长度 idless body 省略 DB assistant `output` 的匹配分支缺少测试覆盖。代码允许 body 缺少 `output`、但模型可见 role/content/tool_calls 与 DB 消息一致时复用 DB refs；现有 folded tool/reasoning 测试主要覆盖 unfolded DB path，不能证明 same-length output-omission 分支。 | testing | 0.78 | `manual -> downstream-resolver`, requires verification |
| 4 | `plugins/filters/async-context-compression/async_context_compression.py:1734` | failed assistant 过滤只测试了 `history.currentId` 重建路径，未测试直接 `chat["messages"]` 路径。实现同时过滤 branch messages 和 direct messages，但当前测试只覆盖 history branch。 | testing | 0.74 | `manual -> downstream-resolver`, requires verification |

### P3 -- Low

| # | File | Issue | Reviewer(s) | Confidence | Route |
|---|------|-------|-------------|------------|-------|
| 5 | `plugins/filters/async-context-compression/async_context_compression.py:2286` | unfolded body 中 assistant `metadata.tool_outputs_trimmed` 的容忍分支缺少正反测试。现有测试覆盖 tool message 的 `metadata.is_trimmed` 和 reasoning exact-match，但没有证明 assistant 内容 mismatch 但带 `tool_outputs_trimmed=True` 时会安全复用，也没有缺少该 metadata 时拒绝复用的负例。 | testing | 0.68 | `advisory -> human` |

## Positive Findings

- 核心修复方向是保守的：无 id body 不会被直接当作可证明 refs 使用，而是先要求 body 与完整 DB branch、或去掉 terminal assistant 后的 user-tip branch 逐条匹配。
- terminal assistant placeholder 只在 body 能证明匹配 user-tip branch 时才被忽略；snapshot 如果覆盖被忽略的 assistant，会在 live refs 校验中被拒绝。
- body/db coverage map 已把 DB 覆盖坐标映射回 body 坐标，inlet 构造 tail 时使用 `_summary_snapshot_current_body_coverage_count()`，避免 folded output 展开后误删可见 tail。
- mismatch、folded tool、folded reasoning、terminal assistant 正向路径、history branch failed assistant 过滤都有直接回归测试。

## Coverage

- 已运行：`../.venv/bin/python -m pytest plugins/filters/async-context-compression/test_async_context_compression.py` -> `106 passed`。
- 未运行 backend 测试。本次可审的 `extensions` 子仓库最新提交只包含插件文件；用户描述中的 `backend/open_webui/utils/middleware.py` SSE `data: [DONE]` 修复与 `backend/open_webui/test/utils/test_llm_error_masking.py` 不在该提交 diff 中，因此本 review 未覆盖该 backend 修复。
- 当前子仓库仍有未提交的无关修改：`docs/zh/future_plugin_development_roadmap_cn.md`，未纳入本次 review。

## Verdict

**Ready with fixes.**

核心的 idless request / terminal assistant placeholder summary reuse 修复没有发现 P0/P1 阻塞问题；但建议在合并前处理两个 P2 代码问题：

1. debug 日志路径改用 `current_refs_for_snapshot`，或在 `current_refs is None` 时跳过 common-prefix debug 计算，并补 `debug_mode=True + 多 snapshot + idless fallback` 回归测试。
2. `convert_output_to_messages()` 的 fallback 展开异常应 fail closed，捕获普通异常并返回不兼容/未展开路径，同时补异常转换测试。

测试覆盖缺口可以随后补齐，但同长度 output-omission 分支和 direct `chat["messages"]` failed assistant 过滤建议优先补上。
