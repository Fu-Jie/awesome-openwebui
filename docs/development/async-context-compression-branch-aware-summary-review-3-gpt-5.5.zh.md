# Async Context Compression Branch-Aware Summary Review 3

日期：2026-06-24  
范围：`async-context-compression` 分支感知摘要复用，重点审查最新的单表 `chat_summary` 存储重构。  
Base：`1437cfdf1f03431dd3e751c665329448cfc5925e`  
模式：`ce:review` interactive

## 意图

本轮变更将摘要存储从 legacy `chat_summary` + `chat_summary_snapshot` 调整为单张 branch-aware `chat_summary` 多行表。旧 count-only `chat_summary` 不能安全复用时会删除重建；可迁移的 `chat_summary_snapshot` 行会迁移进新 `chat_summary` 后删除旧表；无 stable refs 的摘要保存会跳过。

## 结论

当前状态：**Not ready**。

主要阻塞点在数据库升级路径：

- schema inspection 失败会被当作 legacy schema，可能触发破坏性 drop。
- schema 检测只看字段，不检查旧 `chat_id` unique 约束。
- snapshot 迁移信任 legacy hash，可能合并掉不同 `protected_head_count` 的摘要行。
- 缺少真实 SQLite/SQLAlchemy 迁移测试覆盖 DDL/reflection/migration/drop 行为。

## 处理状态

| # | 状态 | 处理说明 |
|---|---|---|
| 1 | addressed | Schema inspection 失败现在返回 unknown，不再触发 drop/recreate；初始化会禁用 summary persistence 并保留现有表。 |
| 2 | addressed | schema 检测会检查 `chat_id` 单列 unique constraint/index；存在时判定为 incompatible 并重建。 |
| 3 | addressed | `chat_summary_snapshot` 迁移时重新解析 refs JSON，并用当前 canonical refs JSON 重算 `covered_refs_hash`。 |
| 4 | addressed | snapshot 迁移只要求核心字段；`branch_tip_id`、`source_current_id`、timestamps、hash 可派生或默认。 |
| 5 | addressed | 新表定义包含 `(chat_id, covered_refs_hash)` unique index；初始化会先清理重复行再确保该 index 存在。 |
| 6 | addressed | `_save_summary` 返回是否持久化成功；未保存时 `_generate_summary_async` 不再发送成功状态。 |
| 7 | addressed | external reference 消息在 refs 生成和 original-history count 中作为 side-channel 跳过，不再阻断 branch-valid save。 |
| 8 | addressed | 初始化失败会保持 `_summary_db_available = False`，load/save 路径短路，避免每次请求重复访问坏 DB 状态。 |
| 9 | addressed | 新增真实 SQLite/SQLAlchemy 迁移测试，覆盖 legacy `chat_summary`、legacy `chat_summary_snapshot`、canonical hash 迁移、旧表删除、unique index。 |
| 10 | deferred | 保留所有历史 branch-valid 摘要是当前产品约束；本轮未引入 retention 裁剪或性能 benchmark，作为后续性能专项。 |

## P1 High

| # | 文件 | 问题 | Reviewer | Confidence | Route |
|---|---|---|---|---:|---|
| 1 | `plugins/filters/async-context-compression/async_context_compression.py:2233` | Schema inspection 失败与“确认是 legacy schema”走同一路径。`get_columns` 瞬时失败、权限问题或方言反射异常时，`_chat_summary_table_is_branch_aware` 返回 `False`，随后 `_init_database` 会 drop `chat_summary`。这会把未知状态误判成可破坏重建。 | reliability | 0.90 | `gated_auto -> downstream-resolver` |
| 2 | `plugins/filters/async-context-compression/async_context_compression.py:2240` | Schema 检测只检查列集合，不检查唯一约束。一个已有所有新字段但仍带 `chat_id` 单列 unique 约束的表会被接受，之后多分支多行保存会失败或退化成单行语义。 | correctness | 0.78 | `manual -> downstream-resolver` |
| 3 | `plugins/filters/async-context-compression/async_context_compression.py:2285` | `chat_summary_snapshot` 迁移信任旧 `covered_refs_hash`。如果旧 hash 没包含 `protected_head_count`，同 refs 但不同 protected head 的摘要可能被当成重复行跳过。迁移时应重新解析 refs JSON，并用当前 canonical refs JSON 重新计算 hash。 | data-migrations | 0.86 | `gated_auto -> downstream-resolver` |

## P2 Moderate

| # | 文件 | 问题 | Reviewer | Confidence | Route |
|---|---|---|---|---:|---|
| 4 | `plugins/filters/async-context-compression/async_context_compression.py:2268` | snapshot 迁移要求 nullable/debug 字段完整，缺少 `covered_refs_hash`、`branch_tip_id`、`source_current_id` 等字段时会放弃整张旧表。实际安全迁移只需要核心字段：`chat_id`、`summary`、`compressed_message_count`、`covered_message_refs_json`；其余可从 refs JSON 派生或默认。 | data-migrations | 0.74 | `gated_auto -> downstream-resolver` |
| 5 | `plugins/filters/async-context-compression/async_context_compression.py:2900` | `_save_summary` 使用 read-then-insert 去重，但 DB 层没有 `(chat_id, covered_refs_hash)` 唯一约束。多 worker 并发保存同一覆盖范围时可能插入重复行。 | reliability, data-migrations | 0.90 | `gated_auto -> downstream-resolver` |
| 6 | `plugins/filters/async-context-compression/async_context_compression.py:5479` | `_save_summary` 在无 refs 时会跳过保存，但调用方仍继续发送“summary loaded / complete”状态。应让 `_save_summary` 返回是否持久化成功，跳过保存时不要发成功状态，或发明确的 skipped 状态。 | correctness | 0.90 | `gated_auto -> downstream-resolver` |
| 7 | `plugins/filters/async-context-compression/async_context_compression.py:1174` | external reference 注入消息带 `is_external_references` metadata，但没有稳定 history ref。它进入 `_message_refs_for_prefix` 后可能导致返回 `None`，从而使带外部引用的回合无法保存 branch-valid summary。应把 external refs 当作 side-channel context，或在 ref counting 中跳过。 | kieran-python | 0.86 | `manual -> downstream-resolver` |
| 8 | `plugins/filters/async-context-compression/async_context_compression.py:2358` | `_init_database` 失败只记录日志，后续 load/save 路径仍会持续访问坏 DB 状态。应记录 `_summary_db_available = False` 一类状态，避免每次请求重复失败和刷日志。 | reliability | 0.86 | `gated_auto -> downstream-resolver` |

## Testing Gaps

| # | 文件 | 问题 | Reviewer | Confidence | Route |
|---|---|---|---|---:|---|
| 9 | `plugins/filters/async-context-compression/async_context_compression.py:2350` | 破坏性 schema upgrade 和 snapshot migration 没有真实数据库状态测试。当前主要是 stub 测试，无法证明 SQLAlchemy reflection、DDL、迁移、drop 的真实行为。 | testing, reliability, data-migrations | 0.95 | `manual -> downstream-resolver` |
| 10 | `plugins/filters/async-context-compression/async_context_compression.py:2978` | retain-all 后 request path 会加载该 chat 的全部 summary rows 和 summary text；没有性能测试或上界验证。大量分支 snapshots 下可能成为热路径瓶颈。 | performance | 0.93 | `manual -> downstream-resolver` |

## 建议修复顺序

1. 修复 schema 检测：区分 `known_compatible`、`known_incompatible`、`unknown/error`；只有 known incompatible 才允许 drop/recreate。
2. 增加 unique constraint/index 检测，拒绝仍带 `chat_id` 单列 unique 的 `chat_summary`。
3. 重写 `chat_summary_snapshot` 迁移：按行解析 refs JSON，重新 canonicalize/hash，派生可派生字段，只跳过无法迁移的行。
4. 让 `_save_summary` 返回持久化结果，调用方根据结果决定是否发成功状态。
5. 增加真实 SQLite migration test，覆盖 legacy `chat_summary`、branch-aware `chat_summary_snapshot`、迁移进新 `chat_summary`、旧表删除、重复迁移幂等。
6. 为 external references + summary save 增加 regression test。

## 已验证

- Review 前实现侧测试曾通过：`.venv/bin/python -m pytest extensions/plugins/filters/async-context-compression/test_async_context_compression.py -q`，结果 `74 passed`。
- Review 是静态审查；reviewer 未执行额外 DB/benchmark 测试。

## Coverage Notes

- 本轮 review 聚焦插件仓库 tracked diff。工作区中 `docs/zh/future_plugin_development_roadmap_cn.md` 存在无关改动，未作为本轮问题来源。
- 无 untracked files 纳入 review。
