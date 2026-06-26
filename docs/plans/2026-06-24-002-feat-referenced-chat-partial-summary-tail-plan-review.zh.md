---
title: 评审：引用长对话时复用部分摘要
type: review
status: complete
date: 2026-06-24
target: docs/plans/2026-06-24-002-feat-referenced-chat-partial-summary-tail-plan.md
---

# 评审：引用长对话时复用部分摘要

## 覆盖范围

已使用以下 reviewer 评审 `docs/plans/2026-06-24-002-feat-referenced-chat-partial-summary-tail-plan.md`：

- `coherence-reviewer`
- `feasibility-reviewer`
- `product-lens-reviewer`
- `scope-guardian-reviewer`
- `security-lens-reviewer`
- `adversarial-document-reviewer`

## 已自动修复

以下 findings 有明确正确的修复方式，已直接应用到计划中：

- 将 read authorization 提升为一等要求：加载、总结或注入 referenced chat 前必须先校验权限。
- 增加 referenced summaries、titles、tail content 的 wrapper-delimiter escaping/quoting 要求。
- 增加 trimming、summarization、fitting 和 fallback 诊断必须 metadata-only 的约束。
- 将 partial-summary tail boundary guidance 从 count-based 改为 ordered covered-refs-based。
- 为 referenced-chat partial summary blocks 增加 protected-head preservation。
- 增加 active-branch-only reference 约束：referenced chats 使用持久化 `history.currentId`，本功能不增加 branch selection，也不根据可用 summaries 推断其他 branch。
- 从 Unit 1 移除 `R10`，让文档更新只由 Unit 5 负责。
- 澄清 branch integration scenario，确保 summary boundary 和 branch tail 之间的 uncovered messages 不会被跳过。
- 增加 unauthorized references、delimiter injection、protected heads、ref/index mismatch、metadata-only diagnostics 的显式测试。
- 增加测试要求：sibling-branch fixtures 必须建模 `history.currentId`，证明 references 使用 saved active branch，并拒绝 non-active sibling summaries，除非它们能验证为 safe common-prefix summaries。

## 后续更新：Active Branch 来源

初轮评审后，计划补充了一个 Open WebUI 行为中的重要前提：

- Referenced chat attachment 只提供 referenced chat id/name，不提供 branch id 或 message id。
- Referenced chat content 从持久化 `history.messages` 和 `history.currentId` 重建。
- 因此，引用 chat 总是指向 referenced chat 保存的 active branch。
- 本功能不为 references 增加 branch picker。

这次更新影响计划中的四处内容：

- `需求追踪`：增加 `R16`，明确 active-branch-only 行为。
- `范围边界` 和 `关键技术决策`：增加显式非目标和决策说明。
- `Unit 2` 和 `Unit 4`：增加 sibling branches 与 `history.currentId` branch switching 测试。
- `Unit 5`：增加文档要求，说明用户不能通过 reference attachment 选择另一个 branch。
- 收紧 Unit 4 的 branch-switching 场景：这里的“切换分支”指的是后续引用前改变 referenced chat 保存的 active branch，不是从 reference attachment 里选择 branch。

## 原始需判断问题

以下是计划加强前的评审问题。当前计划中的处理方式见下方 `决议更新`。

### P2：缺少问题影响证据

**评审器：** product-lens

**位置：** 问题背景

**类型：** 遗漏

**为什么重要：** 如果没有证据证明长 referenced chats 常见或造成实质影响，计划可能把实现和维护成本投入到边缘问题，而不是更高杠杆的 context-quality 问题上。

**证据：**

- “对大对话来说，这会让注入输入爆炸、强制重新调用 LLM 生成引用摘要，或在截断时丢掉有用的旧上下文，即使已经存在一个经过验证的前缀摘要。”
- “目标行为是：优先使用完整 branch-valid summary；如果没有，则使用覆盖范围最大的 branch-valid partial summary，并追加当前分支未覆盖消息的原文 tail。”

**需要决策：** 明确成功信号，例如 token 减少、更少现场生成的引用摘要、更少裁剪，或更好的引用对话回答质量。

### P2：超预算路径削弱 tail 承诺

**评审器：** product-lens

**位置：** 需求追踪 / Unit 3

**类型：** 遗漏

**为什么重要：** 主要用户价值是保留 verified prefix summary 加 uncovered recent tail，但目标场景本身就是可能超预算的长对话。如果这些场景被总结或裁剪时没有明确产品优先级，功能可能在实现层面满足计划，却仍然无法达成用户价值。

**证据：**

- “R2. 引用注入必须包含 selected summary 未覆盖的所有当前分支消息，除非发生显式预算裁剪或 fallback summarization，并记录诊断。”
- “如果 mixed block 不适配，将 mixed block 作为 summary input，使 summary model 同时看到 verified prefix summary 和 original tail。”

**需要决策：** 选择紧预算优先级：保留近期未覆盖 tail 原文、保留较早的摘要上下文，或最大化引用对话的整体召回。

### P2：Summary model 边界缺少隐私决策

**评审器：** security-lens

**位置：** Unit 3

**类型：** 遗漏

**为什么重要：** 当 mixed reference block 超预算时，计划会把 referenced-chat content 发送给配置的 summary model。这可能跨越与 current chat model 不同的 provider 或 tenant 边界。

**证据：**

- “如果 mixed block 不适配，将 mixed block 作为 summary input，使 summary model 同时看到 verified prefix summary 和 original tail。”
- “如果 `partial summary + tail` 放不进预算，优先用配置的 summary model 总结 mixed reference block。”

**需要决策：** 决定 referenced-chat content 是否可以发送给配置的 summary model，是否必须使用 current chat model/provider，或是否需要拒绝/配置模式。

### P2：多引用顺序仍是关键行为

**评审器：** adversarial-document-reviewer

**位置：** 开放问题 / 风险与依赖

**类型：** 遗漏

**为什么重要：** Sequential `remaining_direct_budget` 意味着先处理的 referenced chat 会消耗预算，并迫使后续 references 进入 summary 或 fallback path。如果 metadata order 是偶然的，同一组 references 可能产生不同上下文。

**证据：**

- “多引用如何分配预算？本轮 attachment order 是权威顺序，继续使用现有 sequential `remaining_direct_budget` accounting。”
- “两个 referenced chats 时，attachment order 决定哪个 mixed block 先递减 `remaining_direct_budget`，从而确定性影响第二个 reference 是 direct 还是 summarized。”

**需要决策：** 选择 attachment-order 行为、平均预算、基于优先级的分配或单引用预算上限。

### P2：Generated mixed-summary 缓存策略未决定

**评审器：** adversarial-document-reviewer

**位置：** 开放问题 / 系统影响

**类型：** 遗漏

**为什么重要：** Fallback path 可能从 mixed block 生成摘要，该 mixed block 包含早期摘要加 raw tail。既然现有压缩本来就支持基于旧 summary 加新消息继续生成新 summary，如果这次计算出的摘要不持久化，后续引用同一分支会重复消耗 summary model。

**证据：**

- “Generated mixed-block summary 是否缓存？必须缓存。”
- “从 mixed cached-summary-plus-tail input 生成的 summaries 必须保存到 `chat_summary`，因为这与现有基于旧摘要继续压缩新消息的模型一致。”
- “如果 mixed block 不适配，将 mixed block 作为 summary input。”

**需要决策：** 决定 mixed-input summaries 是否必须持久化，以及持久化时如何保持 branch-aware refs/fingerprints 覆盖语义。

## 决议更新

计划已更新，解决上述 P2 判断项：

- 增加成功指标：direct token 减少、mixed blocks 适配预算时避免调用 summary model，以及 summarized/trimmed tail content 的 metadata-only diagnostics。
- 将紧预算优先级设为尽量保留最新 uncovered tail messages 原文；较早的 summarized context 可先被压缩或省略。
- 保持 provider routing 稳定：mixed referenced-chat fallback summarization 使用现有 configured summary model，不静默切换到 current chat model/provider，本轮也不新增 valve。
- 多引用选择确定性的 attachment-order processing，并使用现有 sequential `remaining_direct_budget` accounting。
- 决定 mixed cached-summary-plus-tail input 生成的 summaries 必须持久化到 `chat_summary`，并写入当前 referenced chat active branch 的覆盖 refs/fingerprints；持久化 normal summary text，不持久化当前请求的注入 wrapper。

## 剩余风险

- 现有 active-chat atomic grouping helpers 看起来可复用于 referenced-chat boundaries，但实现仍需验证 helper semantics 与 referenced-chat formatted blocks 是否匹配。
- 计划有意避免新增 valve。这大概率合适，但 rollout 风险取决于部署中引用超长 chats 的频率。
- Cross-provider referenced-chat summarization 可能有部署特定的隐私影响。
- Active-branch-only 规则依赖持久化 `history.currentId` 是引用时用户期望的 branch；如果未来用户希望每次 reference 单独选 branch，那应作为独立 Open WebUI/UI 功能，而不是本插件改动的一部分。
