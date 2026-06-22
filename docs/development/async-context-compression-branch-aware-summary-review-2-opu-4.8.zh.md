---
title: Async Context Compression 分支感知摘要复用 — 独立审查（计划 / 既有 review / 代码实现）
date: 2026-06-22
status: partially-addressed
reviewer: opus-4.8 (ce:review, interactive / report-only document)
---

# Code Review Results

## 修复后更新（2026-06-23 ce:work address review）

本轮按本 review 的 actionable findings 修复了安全/可靠性快赢项并补齐相应测试，保留下方原始审查记录作为追踪上下文。测试：`pytest` **58 passed**（原 53 + 新增 5）。

| Finding | Status | Resolution |
|---|---|---|
| P1 #1 native tool-call ref 身份 | **deferred（已验证为真，析因完成）** | 复核 OpenWebUI `utils/misc.py:convert_output_to_messages`，确认展开消息无 `id`；并确认 inlet 用 folded 消息（真实 id）、outlet 用 unfolded 消息选/存 refs，是 folded↔unfolded 表征不一致问题。证明「合成 id」方案会破坏 sibling/deleted 判别（不安全），正确修法须用与 history graph 对齐的 folded refs 并打通坐标，属设计级改动；当前行为安全降级（不注入错误摘要），建议用 /ce:plan 在真实 native 运行态下专项落地。 |
| P2 #2 marker-drop overclaim | **addressed** | budgeting 丢弃内嵌 summary marker 时置 `summary_marker_dropped`，保存阶段强制 `covered_refs=None`，只落 compatibility pointer，不再固化越界覆盖。新增 `test_generate_summary_async_skips_snapshot_when_marker_dropped_for_budget`。 |
| P2 #3 retention 驱逐短前缀 | **addressed** | `_summary_snapshots_to_prune` 在 recency+size 截断后无条件保留 `compressed_message_count` 最小的 snapshot。新增 `test_snapshot_retention_protects_stale_shortest_prefix`。 |
| P2 #4 prune 回滚 save | **addressed** | `_prune_summary_snapshots_async/_sync` 包入 try/except，prune 失败只 warning 不传播，不再回滚已暂存的 snapshot 写入。 |
| P2 #5 async 未 expunge | **addressed** | `_load_summary_snapshots` async 路径返回前 `session.expunge_all()`，与 sync 对齐，避免会话关闭后属性访问触发 DetachedInstanceError。 |
| P2 #6 安全不变量测试盲区 | **partially addressed** | 新增 R4 deleted-vs-sibling 双判别（`test_snapshot_selection_discriminates_deleted_vs_sibling`）、R5 image-only 编辑（`test_snapshot_selection_rejects_image_only_edit`）。R7 atomic-group 拒绝、R9 两分支往返、save-path fingerprint 断言等仍未补。 |
| P3 #7 hash 漏 protected_head_count | **addressed** | snapshot dedup 键改为 `sha256(refs_json)`（含 head count），相同 refs 不同 head count 不再 clobber。新增 `test_save_summary_dedup_hash_differs_for_protected_head_count`。 |
| P3 #9 fingerprint 漏 images | **addressed** | `_message_fingerprint` payload 加入 `images`，原地改图可被检测。覆盖于 #6 image 测试。 |
| P3 #8/#10/#11/#12–#16 | **open** | #8 当前 fail-closed 安全、不动；#10 lazy 建表并发/阻塞、#11 跨进程锁、#12–#16 可维护性重构未做（避免在 mid-flight 特性上引入额外 churn），保留为后续项。 |

> 修复阶段未改动 DB schema，未升版本号（特性整体仍在工作树未提交，版本/提交由作者在最终定稿时统一处理）。

---

## 审查范围（Scope）

`/Users/nex/orca/workspaces/open-webui/extensions/extensions` 工作树中 `async-context-compression` 分支感知摘要复用改动（vs `HEAD`，即 upstream `78b1d87` 基线之上的未提交改动）。本次审查同时覆盖三个对象，对应用户要求：

1. **改动计划**：`docs/development/async-context-compression-branch-aware-summary-plan.zh.md`
2. **既有 review 文档**：`docs/development/async-context-compression-branch-aware-summary-review-1-gpt-5.5.zh.md`（gpt-5.5 出具，状态标记为 `addressed`）
3. **代码实现**：`plugins/filters/async-context-compression/async_context_compression.py` 与 `test_async_context_compression.py`（实现 +973 行，测试 +1062 行），及 `README.md` / `README_CN.md`。

排除与本特性无关的改动：`docs/zh/future_plugin_development_roadmap_cn.md`。

> 本文档为 **report-only** 性质（只产出审查结论，不修改实现代码）。

## 意图（Intent）

OpenWebUI 的聊天历史是消息图（`history.messages` 映射 + `currentId` 叶子 + `parentId` 祖先链 + `childrenIds` 兄弟分支）。upstream 的 count-only 摘要复用无法判断缓存摘要覆盖的是哪条分支。本改动改为按分支保存 **snapshot**，每个 snapshot 携带有序 covered refs（`message_id` + payload `fingerprint`）；inlet 只有当 snapshot 的全部 refs 都能解释为「当前活跃祖先（顺序匹配）」或「在完整 history graph 中证明已删除」时才复用，任何 live sibling ref 或原地编辑（fingerprint 变化）都必须拒绝。最终请求 = protected head（`keep_first`） + 已验证 summary marker + 原文 live tail。

## 审查方法与执行验证

- 主审查（opus-4.8）通读核心路径：`_snapshot_coverage_for_current_branch`、`_message_refs_for_prefix`、`_select_applicable_summary_snapshot`、`_save_summary`、`_generate_summary_async`、outlet 重注入、`_unfold_messages` 与 ref/fingerprint helpers。
- 并行分发 6 个 persona sub-agent（sonnet）：correctness、adversarial、testing、reliability、kieran-python、data-migrations。
- **测试执行**：`mise exec -- python -m pytest plugins/filters/async-context-compression/test_async_context_compression.py -q` → **53 passed in 0.39s**。
- 对最高影响的几条结论（native tool-call ref 身份、prune 事务、hash 去重键）由主审查独立复核代码确认。

## 总体判断（先读这段）

实现质量高，核心方向正确：snapshot + 完整 refs 验证确实解决了「只校验一个边界不够」的根本问题，`_snapshot_coverage_for_current_branch` 对 deleted / sibling / edited / out-of-order 四类情况的判定经独立 trace 是正确的，gpt-5.5 review 提出的两个保存语义缺口（reinjected successor、protected head 覆盖）也已被真实修复并通过验证。

但 gpt-5.5 review 把状态标为 `addressed` 是 **过早** 的：本次独立审查发现 **一个会让整个特性对 native tool-calling 聊天静默失效的结构性缺口（P1/P2）**，以及若干会影响可靠性与长期复用率的问题（prune 事务回滚、async 会话 expunge、retention 驱逐短前缀 snapshot）。这些是 gpt-5.5 review 没有触及的维度。

---

## 发现（Findings）

### P1 — Critical / 接近 Critical

| # | File | Issue | Reviewer | Confidence | Route |
|---|------|-------|----------|------------|-------|
| 1 | `async_context_compression.py:5266` / `:1213` / `:4589` | **native tool-calling 聊天永远无法生成或选中 branch-valid snapshot，特性对该用例静默失效。** outlet 在 native 模式下用 `_unfold_messages` 把带 `output` 的 assistant 消息展开成 `[assistant(tool_calls), tool, assistant]` 合成子消息（`convert_output_to_messages(..., raw=True)`，line 4589 / 3477），这些合成消息没有稳定 `id`。`_generate_summary_async` 用展开后的 `summary_messages` 计算 `covered_refs = _message_refs_for_prefix(messages, saved_compressed_count)`（5266）；只要被覆盖前缀里含任一展开后的工具消息，`_message_ref` 返回 None（1066-1071），`_message_refs_for_prefix` 整体返回 None（1213），于是只落 compatibility `chat_summary` 行、**不写 snapshot**（5270 仅 warning）。对称地，inlet 侧 `_current_branch_refs` 对同样的 id-less 视图也会返回 None，使 `_select_applicable_summary_snapshot` 在 1426 处直接放弃。结果：含原生工具调用的长对话拿不到任何压缩收益（恒发原始上下文），与插件 v1.4.0 主打的 atomic tool-call 支持和计划手工验证场景「native tool-calling 跨过压缩阈值后 snapshot 仍有效」直接冲突。**附带隐患**：folded（带 `id`，fingerprint 含 `output`）与 unfolded（无 id）对同一逻辑内容产生不同 ref 身份，inlet/outlet 视图不一致会进一步放大该问题。 | adversarial + 主审查 | 0.85 | `manual -> downstream-resolver`（requires-verification） |

> 严重度说明：该缺口**不会注入错误摘要**（安全降级为原文上下文），因此不是数据正确性 P0；但它让特性对一整类核心用例失效，且与需求 R7 / 手工验证场景冲突，按「合并前必须确认并给出结论」定为 **P1**。务必先验证 `convert_output_to_messages(raw=True)` 是否真的丢弃 `id`，再决定修法（在展开时把原始 `id` 复制到第一个展开消息，或对 covered_refs 计算使用 pre-unfold 的原始消息）。

### P2 — High

| # | File | Issue | Reviewer | Confidence | Route |
|---|------|-------|----------|------------|-------|
| 2 | `async_context_compression.py:5250` / `:5169` | **token-fit 丢弃内嵌 summary marker 后，`saved_compressed_count` 过度声明覆盖范围。** 当 summary 模型预算紧张、循环把内嵌 marker 从 `middle_messages` 移除（5169-5171，`protected_prefix→0`、`previous_summary=None`）后，LLM 只看到新 tail，生成的摘要只覆盖新 tail；但 `saved_compressed_count = base_progress + len(new_tail)`（5250-5252），`covered_refs`（5266 从仍含 marker 的 `messages` 取）记录 `base_progress + new_tail` 全量 refs。下次 inlet 选中该 snapshot 时，`base_progress` 段会被一个从未描述它的摘要隐藏，造成历史静默丢失。pre-existing 的坐标公式问题，但新的 covered_refs 机制把这个 overclaim **固化进 DB**，更难在读侧发现。 | correctness | 0.80 | `manual -> downstream-resolver`（requires-verification） |
| 3 | `async_context_compression.py:1348` | **retention 驱逐分支切换所需的「短公共前缀」snapshot。** `_summary_snapshots_to_prune` 仅按 `(updated_at DESC, compressed_message_count DESC)` 保留前 20 个（1358-1369）。长分支上累积的较新、较长 snapshot 会把覆盖更短公共前缀、但更旧的 snapshot 挤出。当用户在较早消息处分叉到新分支时，恰恰需要那个短前缀 snapshot 来复用公共祖先——它已被删除，于是新分支退化为恒发原文。这与计划 Unit 3 明确写的「优先保留更新、更大、**可精确复用的前缀** snapshots」不符；实现漏掉了「保护短前缀」这一维度。 | adversarial | 0.80 | `gated_auto -> downstream-resolver` |
| 4 | `async_context_compression.py:2754` / `:2818` | **prune 抛异常会回滚同一事务里尚未提交的 snapshot 保存。** `_prune_summary_snapshots_async/_sync` 在 `_save_summary` 的 `await session.commit()`（2760）**之前**、同一 `async with session` 事务内执行裸 `execute/delete`，自身无 try/except。一次瞬时锁竞争 / 序列化失败会让异常冲出 `async with`，触发回滚，新 snapshot 与 pointer 一起丢失；外层 `except`（2828）只 `logger.error` 且后台任务静默返回，用户无感。在已累积 21+ snapshot 的 chat 上每次保存都走 prune，放大该风险。 | reliability | 0.85 | `gated_auto -> downstream-resolver` |
| 5 | `async_context_compression.py:2838` | **async 会话路径加载 snapshot 后未 expunge，可能 DetachedInstanceError。** sync 路径逐个 `session.expunge(snapshot)`（2846-2850），async 路径直接 `list(result.scalars().all())` 返回（2838-2841）。`_select_applicable_summary_snapshot` 在会话关闭后访问 `covered_message_refs_json`、`compressed_message_count`、`branch_tip_id` 等属性；对 expired/detached 对象的惰性列访问会抛 `DetachedInstanceError`，经无内层 handler 一路冒泡到 inlet/outlet 外层 except → 降级原文。安全但静默，且 OWUI ≥0.9.0（async 会话）是主要目标。需用真实 AsyncSession fixture 验证（当前测试用 fake，未触发会话生命周期）。 | reliability | 0.70 | `gated_auto -> downstream-resolver`（requires-verification） |
| 6 | `test_async_context_compression.py`（多处） | **关键安全不变量缺乏直接测试，存在「回归不被发现」的盲区。** 53 个测试通过，但多个安全门只被间接覆盖：① R4 第二判别（covered ref **仍存在于完整 graph 但不在当前链上 = sibling 必须拒**）只测了「完全删除」一侧（test:745 的 `live_message_refs_by_id` 仅由 current 构造）；② R7 「coverage 切开 atomic tool group 时 `_select_applicable_summary_snapshot` 拒绝」（1497-1507）零覆盖；③ R8「null/empty covered refs 的 legacy snapshot 必须被选择侧拒绝」「count 超当前分支长度」无测试；④ 保存路径只断言 ref `id`，不断言 `fingerprint`（空 fingerprint 会让所有未来 snapshot 失效却仍 pass）；⑤ token-fit shrink 改变 `saved_compressed_count` 后 refs 边界无测试；⑥ R9 两分支各持 snapshot、切回各选其一的往返无测试；⑦ 损坏 refs JSON（`_parse_message_refs_json` except 分支）无测试。 | testing | 0.85 | `manual -> downstream-resolver` |

### P3 — Moderate / Low

| # | File | Issue | Reviewer | Confidence | Route |
|---|------|-------|----------|------------|-------|
| 7 | `async_context_compression.py:2689` | **`covered_refs_hash` 去重键忽略 `protected_head_count`，可让有效 snapshot 永久不可用。** upsert 键 `refs_hash = _message_refs_hash(normalized_refs)`（2689）只哈希 refs 列表。同一覆盖范围在不同 `keep_first` 下可产生**相同 refs 但不同 protected_head_count**（例：messages=[m0..m4], target=4；keep_first=0→refs=[m0..m3],head=0；keep_first=2→start=2,saved_count=2+2=4,refs=[m0..m3] 相同,head=2）。第二次保存命中同 hash 行并覆盖 `protected_head_count`。若 0 被覆盖成 2，之后在 keep_first=0 时该 snapshot 被 1462 的门 `protected_head_count > effective_keep_first` 永久拒绝。安全但导致复用率下降。 | correctness + data-migrations | 0.85 | `safe_auto -> review-fixer` |
| 8 | `async_context_compression.py:1232` | **`_history_graph_refs_by_id` 对任一 id-less 节点 fail-closed 整图返回 None。** 只要完整 graph 里有一个无法解析 id 的节点（如系统/工具注入节点），整个 `live_message_refs_by_id` 变 None，使所有「含已删除 ref」的 snapshot 被保守拒绝（1312-1317），该 chat 压缩静默失效。语义上安全（fail-closed 正确），但过度保守；可改为 `continue` 跳过单个无法识别节点构建部分 graph（无 id 节点不可能成为 sibling 风险）。与 #1 叠加放大。 | reliability | 0.75 | `gated_auto -> downstream-resolver` |
| 9 | `async_context_compression.py:1046` | **`_message_fingerprint` 漏掉独立 `images` 字段，原地改图不被检测（R5 缺口）。** payload 含 role/content/output/tool_calls/tool_call_id/files/sources，但无 `images`。若用户仅替换消息附带的图片而文本不变，fingerprint 不变，旧摘要被当作有效覆盖复用。confidence 偏低，因现代 OWUI 多在中间件把 images 归一进多模态 content（会顺带触发 content 变化）；但 DB-loaded 路径不一定归一。建议把 `images` 纳入 fingerprint。 | adversarial | 0.62 | `safe_auto -> review-fixer` |
| 10 | `async_context_compression.py:2157`(lazy create) / `:520`(model) | **新表 `chat_summary_snapshot` 的迁移/并发/事务边界细节。** ① 多 worker 启动时 `inspect.has_table` 与 `create(checkfirst=True)` 非原子，PostgreSQL 上第二个 worker 的 CREATE 可能抛 DuplicateTable，被宽 except 吞掉但产生误导性 `Initialization failed` 噪声日志；② init 在 `__init__` 同步执行 `inspect`/`create`，OWUI≥0.9.0 异步上下文下阻塞事件循环；③ init 失败未置标志位，后续每条消息重试失败 INSERT → 错误风暴；④ 缺 `(chat_id, covered_refs_hash)` 复合/唯一约束，去重靠 SELECT-then-INSERT 有 TOCTOU 窗口（跨进程锁无效）；⑤ `covered_message_refs_json` NOT NULL 无 server_default，仅靠运行时 guard。 | data-migrations + reliability | 0.80 | `gated_auto -> downstream-resolver` |
| 11 | `async_context_compression.py:857` / `:2726` | **跨进程并发：per-chat `asyncio.Lock` 是实例级，多 worker 下同一 chat 可并发跑摘要任务。** dedup 靠 `covered_refs_hash`，多数情况避免覆盖，但 READ COMMITTED 下两个相同键 INSERT 可都成功产生重复行（正确性无损，仅表膨胀 + 扰乱 prune recency）；外部引用摘要保存又在 per-chat 锁之外。pre-existing 架构限制，被新 snapshot 路径继承。 | adversarial + reliability | 0.72 | `advisory -> human` |
| 12 | `async_context_compression.py:1265` | `_snapshot_coverage_for_current_branch` 返回裸 `tuple[int,int,Optional[str]]`，三槽语义（matched / skipped / reject reason）靠位置解包，可读性弱。建议 `NamedTuple`/`dataclass`。 | kieran-python + maintainability | 0.85 | `advisory -> human` |
| 13 | `async_context_compression.py:1371` | `_annotate_summary_snapshot_selection` 用 `setattr/getattr` 把 `_current_coverage_*` 瞬态状态 monkey-patch 到 ORM 实例上：对类型系统不可见、对 ORM dirty-tracking 不可见，且 fallback 路径取的是**另一语义**（DB 原值）。建议引入 `SelectedSnapshot` 包装 dataclass，消除三个 `_summary_snapshot_current_*` 取值器的 getattr fallback。 | kieran-python | 0.85 | `advisory -> human` |
| 14 | `async_context_compression.py:2668` | `_save_summary` 的 async/sync 两分支 snapshot upsert + prune 体几乎逐行重复（2725-2758 vs 2791-2818，含重复的 debug 日志），改一处漏一处的维护风险。建议抽共享 helper。 | kieran-python | 0.85 | `advisory -> human` |
| 15 | `async_context_compression.py:~1115` | `covered_message_refs_json` 双格式（裸 list / `{refs, protected_head_count}` 对象）无版本标记，靠形状推断；未来 parser 漏掉 list 分支会静默对所有旧行返回空 refs。建议统一为对象形态（head=0 时也写），删除双解析分支。 | kieran-python + data-migrations | 0.82 | `advisory -> human` |
| 16 | `async_context_compression.py:1340` vs `:1362` | 选择键 `_summary_snapshot_selection_key`=`(count, ts)` 与 prune 键=`(ts, count)` 优先级相反；可能保留 20 个较新小覆盖 snapshot 却丢弃一个本会被选中的大覆盖 snapshot。与 #3 同源，建议对齐或在两处加策略注释说明刻意差异。 | kieran-python | 0.80 | `advisory -> human` |

---

## 计划文档审查（`...-plan.zh.md`）

计划质量很高：准确刻画了 count-only 的根因（数组坐标 ≠ 分支身份）、R1–R10 完整且自洽、mismatch 三场景（分叉 / 原地编辑 / 删除）推理严谨、「被考虑但不采用」与「延后到实现」分区合理。以下是计划自身的盲点 —— 它们直接传导成了上面的实现缺口：

- **未协调既有 `_unfold_messages` 与新 ref 身份要求（→ 对应 P1 #1）。** Unit 2 写「history map value 缺少嵌入 `id` 时，refs 使用 map key」，但 native 工具调用展开出的合成子消息**既无 `id` 也无 map key**。计划没有把「展开后子消息如何获得稳定身份」这一关键路径纳入设计，是最大盲点。
- **retention 规则只实现了一半（→ 对应 P2 #3 / P3 #16）。** Unit 3 要求「优先保留更新、更大、**可精确复用的前缀** snapshots」，但实现只做了 recency+size，丢掉了「保护短公共前缀」语义，恰好破坏分支切换复用——而这正是计划成功标准的核心场景之一。
- **prompt-fitting 改变覆盖范围只覆盖了一个子情形（→ 对应 P2 #2）。** Unit 5 正确指出「fitting 丢弃最新 atomic groups 时 refs 必须排除」，但漏掉了「丢弃内嵌 previous-summary marker」这个子情形下 `saved_compressed_count` 仍含 `base_progress` 的 overclaim。
- 「完整 history graph 获取路径」作为延后问题处理得当；实现确实加载了完整 graph 并在缺失时 fail-closed。这点计划与实现一致且正确。

结论：计划作为技术方向文档是 **可靠的**，但应补一节明确「native 工具调用展开消息的身份策略」与「retention 必须显式保护最短可复用前缀」，否则实现会继续踩这两个坑。

## 既有 review 文档审查（`...-review-1-gpt-5.5.zh.md`）

- **真实修复已确认有效**：经独立复核，`_message_refs_for_prefix` 的 marker-overlap 逻辑（1203-1210，重叠不一致才 fail-closed）确实让 reinjected view 能保存 branch-valid successor；`protected_head_count` 的存储 + 选择门（1459-1469）确实修复了「protected head 被声明覆盖却不在 prompt」的语义。gpt-5.5 的两条主结论与修法是正确的。
- **`status: addressed` 与「Ready」过早**：该 review 的维度集中在保存语义（correctness/testing/maintainability），**未触及** native tool-call ref 身份（P1 #1）、retention 驱逐短前缀（P2 #3）、prune 事务回滚（P2 #4）、async expunge（P2 #5）。把整个改动标为已闭环会掩盖这些合并阻断项。建议把该文档 `status` 回退为 `superseded` 或在其顶部追加指向本审查的「仍有未决项」批注。
- **该文件正被删除**：git 状态显示 `...-review.zh.md` 为 `AD`（index 增、worktree 删），`...-review-1-gpt-5.5.zh.md` 为未跟踪新增——即正在用带模型后缀的新命名替换旧 review。内容（addressed 摘要表 + verification）已保留，删除本身可接受；只需确认删除的是旧路径而非有效记录。
- 次要：该 review 用了非标准 severity 标签（high/medium 与 P 级混用）且 plan source 标 `inferred`；本审查改用 P0–P3 + 明确 route。

---

## 需求完整性（Requirements Completeness）

Plan source: **explicit**（用户显式指向 `...-plan.zh.md`）。

| 需求 / 单元 | 状态 | 说明 |
|---|---|---|
| R1 保留所有未被证明覆盖的当前分支消息 | met | 选择失败即回退原文；`_message_refs_for_prefix`/边界逻辑正确。 |
| R2/R3 snapshot 全 refs 可解释、live sibling 必拒 | met（核心逻辑）/ 测试弱 | `_snapshot_coverage_for_current_branch` 四类判定经 trace 正确，但 R4 第二判别（sibling vs deleted）缺直接测试（#6①）。 |
| R4 删除可跳过、分叉不可跳过 | partially | 实现正确依赖完整 graph 区分；但「id 仍在 graph、不在当前链」的拒绝分支未测（#6①）。 |
| R5 原地编辑使 snapshot 失效 | partially | fingerprint 覆盖主要字段，但漏 `images`（#9）。 |
| R6 切换/编辑/重生/删除后 live tail 原文保留 | met / 断言弱 | 行为正确，但测试只断言 tail 的 id 不断言 content（#6）。 |
| R7 system / external ref / atomic tool group 不变量 | **at risk** | atomic-group 切割拒绝逻辑（1497-1507）存在但**零测试**；更严重的是 native tool-call 链根本进不了 snapshot（P1 #1），与 R7 精神冲突；gap 内 system 消息保留无测试（#6）。 |
| R8 legacy summary 安全降级、不隐藏 live tail | partially | 写侧不信任 legacy pointer；但选择侧拒绝 null-refs/超长 count 的 legacy snapshot 无测试（#6③）。 |
| R9 每分支各持 snapshot、切回可复用 | **at risk** | 选择支持，但 retention 会驱逐切回所需短前缀（P2 #3），两分支往返无测试（#6⑥）。 |
| R10 late async 任务不破坏其他分支状态 | partially | hash 隔离基本成立；但多进程锁失效（#11）+ 非 clobber 无测试（#6）。 |

## 残余可执行项（Residual Actionable Work）

| # | 关联 | Issue | Route | 下一步 |
|---|------|-------|-------|--------|
| 1 | #1 | native tool-call 链无 snapshot | `manual -> downstream-resolver` | 先验证 `convert_output_to_messages(raw=True)` 是否丢 `id`；若是，展开时把原 `id` 赋给首个展开消息，或对 covered_refs 用 pre-unfold 原始消息。补 native 链能存且能选中 snapshot 的回归。 |
| 2 | #2 | marker-drop 后 overclaim | `manual -> downstream-resolver` | marker 被丢弃（5170）时置标志，`saved_compressed_count` 用 `len(new_tail)`，covered_refs 仅取新 tail。 |
| 3 | #3/#16 | retention 驱逐短前缀 | `gated_auto -> downstream-resolver` | recency 截断后，无条件保留 `compressed_message_count` 最小的 snapshot；或按前缀长度分桶各留一个。对齐选择/prune 排序语义。 |
| 4 | #4 | prune 回滚 save | `gated_auto -> downstream-resolver` | 把 `_prune_summary_snapshots_*` 包进独立 try/except 并 log，确保 prune 失败不阻断主写入；或移出保存事务。 |
| 5 | #5 | async 未 expunge | `gated_auto -> downstream-resolver` | async 路径 `session.expunge_all()`（或 `noload('*')`），与 sync 对齐；加真实 AsyncSession 测试。 |
| 6 | #6 | 安全不变量测试盲区 | `manual -> downstream-resolver` | 按 #6 ①–⑦ 逐项补测，重点 R4 sibling 判别、atomic-group 拒绝、save-path fingerprint 断言、token-fit-shrink 边界。 |
| 7 | #7 | hash 漏 head count | `safe_auto -> review-fixer` | upsert 键改用整个 `refs_json` 计算，或把 `protected_head_count` 并入 hash 输入。 |

## 覆盖与残余风险（Coverage）

- **Suppressed**：confidence < 0.60 的项均未入表（adversarial 的 images 项 0.62 保留为 P3 #9）。
- **测试现状**：53 passed（pytest 0.39s）。但测试整体偏 helper 层与 fake 会话，缺真实 async 会话生命周期、save→reload→select 跨生命周期、native tool-call 端到端验证。
- **残余风险**：多进程部署下 per-chat 锁与 hash 去重的竞态（#11）；DB 瞬时不可用时 `_load_chat_history_live_refs` 返回 None 导致一次请求内所有含删除 ref 的 snapshot 被保守拒绝（安全、仅性能）；长对话 graph `deepcopy` 的 CPU/内存压力（`_history_graph_refs_by_id` 每节点 deepcopy，inlet/outlet 热路径各调一次）。
- **Reviewer**：correctness、adversarial、testing、reliability、kieran-python、data-migrations 均返回；主审查对 #1/#4/#7 做了独立代码复核。无 reviewer 失败。

---

> **Verdict: Not ready（与 gpt-5.5 review 的 addressed 状态相比，存在新增合并阻断项）**
>
> **Reasoning:** 核心分支安全逻辑（snapshot + 全 refs 验证）方向正确、关键判定经验证无误，gpt-5.5 的两处保存语义修复也属实。但本次独立审查发现 **native tool-calling 聊天会让整个特性静默失效（P1 #1）**——这是一类核心用例，且与 R7 及计划手工验证场景直接冲突；同时 prune 事务回滚（#4）、retention 驱逐短前缀（#3）、async 会话 expunge（#5）会侵蚀长期复用率与可靠性。这些都不会注入错误摘要（安全降级），但会让特性「对该用 case 不工作」或「越用越退化」。
>
> **Fix order:** 先确认并修 #1（native tool-call ref 身份，决定特性是否真正可用）→ #4（prune 不得回滚主写入）→ #2（marker-drop overclaim）/ #3（retention 保护短前缀）→ #5（async expunge）→ #7（hash 去重键）→ #6 补齐安全不变量测试 → #9–#16 可维护性整改。
