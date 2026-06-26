# 异步上下文压缩过滤器

| 作者：[Fu-Jie](https://github.com/Fu-Jie) · v1.7.1 | [⭐ 点个 Star 支持项目](https://github.com/Fu-Jie/openwebui-extensions) |
| :--- | ---: |

| ![followers](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_followers.json&label=%F0%9F%91%A5&style=flat) | ![points](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_points.json&label=%E2%AD%90&style=flat) | ![top](https://img.shields.io/badge/%F0%9F%8F%86-Top%20%3C1%25-10b981?style=flat) | ![contributions](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_contributions.json&label=%F0%9F%93%A6&style=flat) | ![downloads](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_downloads.json&label=%E2%AC%87%EF%B8%8F&style=flat) | ![saves](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_saves.json&label=%F0%9F%92%BE&style=flat) | ![views](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_views.json&label=%F0%9F%91%81%EF%B8%8F&style=flat) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |

> **重要提示**：为了确保所有过滤器的可维护性和易用性，每个过滤器都应附带清晰、完整的文档，以确保其功能、配置和使用方法得到充分说明。

本过滤器通过智能摘要和消息压缩技术，在保持对话连贯性的同时，显著降低长对话的 Token 消耗。

## 使用 Batch Install Plugins 安装

如果你已经安装了 [Batch Install Plugins from GitHub](https://openwebui.com/posts/batch_install_plugins_install_popular_plugins_in_s_c9fd6e80) ，可以用下面这句来安装或更新当前插件：

```text
从 Fu-Jie/openwebui-extensions 安装插件
```

当选择弹窗打开后，搜索当前插件，勾选后继续安装即可。

> [!IMPORTANT]
> 如果你已经安装了 OpenWebUI 官方社区里的同名版本，请先删除旧版本，否则重新安装时可能报错。删除后，Batch Install Plugins 后续就可以继续负责更新这个插件。

## 分支感知摘要复用

- **分支安全的缓存摘要**：只有当已保存摘要行里的每个 message id + payload fingerprint ref 都能解释为当前活跃分支祖先，或能从完整 history graph 证明已经删除时，缓存摘要才会被复用。仍包含 live sibling 分支 refs 的摘要行会被拒绝，因此新增或编辑后的当前分支消息必须留在原文 live tail 里，不能被旧摘要隐藏。
- **单表持久化**：分支专属的可复用覆盖范围以多行形式写入 `chat_summary`；不再保留单独的 current pointer 行。插件会保留 branch-valid 历史摘要行，使用户从更早位置分叉时仍能复用当前分支上最接近的祖先摘要。
- **受保护头部追踪**：摘要行会记录有多少开头消息是在摘要之外按原文保留的。如果当前 `keep_first` 策略已经不再保留这些消息，该摘要行不会作为 branch-valid 覆盖范围复用。
- **安全升级行为**：没有覆盖范围元数据的 legacy summary 不再被当成可信覆盖。升级后的第一轮对话可能会发送更多原始上下文，直到生成 branch-valid 摘要行。

## 1.7.1 版本更新

- **分支感知摘要复用**：缓存摘要会先用有序 message refs 和 payload fingerprints 校验，来自 sibling 分支或编辑前历史的摘要不会注入到错误分支。
- **单表摘要存储**：branch-valid 历史摘要行直接保存在 `chat_summary`，所有分支摘要都在这张表里。
- **分支感知引用聊天**：引用聊天现在可以复用当前 active branch 上最大的有效前缀摘要，并拼接未覆盖的原文 tail。如果因此生成 continuation summary，会写回被引用聊天自己的 `chat_summary`，后续引用可直接复用。
- **修复无 id 请求的摘要复用**：当 request body 没有稳定 message id 时，插件会先用数据库里的 active branch 严格对齐校验，再决定是否复用已有摘要，避免长对话误退回原始全文。
- **处理末尾 assistant 占位消息**：OpenWebUI 可能先把“正在生成中”的 assistant 占位消息写入数据库，但实际发给模型的 body 只到最新 user message。现在只有在 body 能证明匹配 user-tip 分支时，才会忽略这个末尾占位消息。
- **更安全的 schema 和 DB fallback 行为**：legacy count-only 摘要不会被当成可信覆盖，旧的一 chat 一行 schema 会安全重建；folded output 转换异常会 fail closed，idless fallback 的 debug 日志不会中断请求。

## 1.6.5 版本更新

- **新增压缩风格控制**：新增 `compression_style` 配置项，支持 `aggressive`、`balanced`、`faithful` 三档，可以直接控制摘要更偏“省 token”还是更偏“保留上下文细节”。
- **新增 faithful 提示词模式**：当 `compression_style=faithful` 时，摘要 prompt 会明确要求模型更多保留关键论证链、评估标准、仍在比较中的候选方案和细微上下文，而不是过度抽象化。

## 1.6.4 版本更新

- **更稳健的摘要响应解析**：后台摘要现在会从多种 provider 返回结构中提取文本，包括标准的 `choices[].message.content`、带 `output_text` 的 content parts，以及 Responses 风格 `output` 里的 message 内容。
- **更安全的 reasoning 过滤**：`reasoning_content`、`thinking` 和 reasoning 类型 output 会被明确忽略，避免把模型思考过程写入聊天记忆。
- **更清晰的空摘要诊断**：如果摘要模型没有返回任何可用文本，过滤器现在会报告精简后的响应结构，而不是抛出含义模糊的通用格式错误。

## 1.5.0 版本更新

- **外部聊天引用摘要**: 新增对引用聊天上下文的摘要支持。现在可以复用缓存摘要、直接注入较小引用聊天，或先为较大的引用聊天生成摘要再注入。
- **快速多语言 Token 预估**: 新增混合脚本 Token 预估链路，使 inlet / outlet 的预检可以减少不必要的精确计数，同时比旧的粗略字符比值更接近真实用量。
- **更稳健的工作记忆提示词**: 重写 XML 摘要提示词，增强普通聊天、编码任务和连续工具调用场景下的关键信息保留能力。
- **更清晰的前端调试日志**: 浏览器控制台日志改为分组化、结构化展示，排查上下文压缩行为更直观。
- **更安全的工具裁剪默认值**: 原生工具输出裁剪默认开启，并新增 `tool_trim_threshold_chars` 配置项，默认阈值为 600 字符。
- **更稳妥的引用聊天回退**: 当新的引用聊天摘要路径生成失败时，不再拖垮当前请求，而是自动回退为直接注入上下文。
- **更准确的摘要预算**: `summary_model_max_context` 现在只负责摘要输入窗口，`max_summary_tokens` 继续只负责摘要输出长度。
- **更容易发现摘要失败**: 重要的后台摘要失败现在会强制显示到浏览器控制台 (`F12`)，并同步给出状态提示。

---

## 核心特性

- ✅ **全方位国际化**: 原生支持 9 种界面语言。
- ✅ **自动压缩**: 基于 Token 阈值自动触发上下文压缩。
- ✅ **异步摘要**: 后台生成摘要，不阻塞当前对话响应。
- ✅ **持久化存储**: 复用 Open WebUI 共享数据库连接，自动支持 PostgreSQL/SQLite 等。
- ✅ **灵活保留策略**: 可配置保留对话头部和尾部消息，确保关键信息连贯。
- ✅ **分支感知注入**: 只在摘要覆盖范围匹配当前活跃分支时，将历史摘要注入到新上下文中。
- ✅ **外部聊天引用摘要**: 支持复用 branch-valid 完整摘要、partial summary + active-branch tail、小聊天直接注入，以及大聊天生成并持久化摘要后注入。
- ✅ **结构感知裁剪**: 智能折叠过长消息，保留文档骨架（标题、首尾）。
- ✅ **原生工具输出裁剪**: 支持裁剪冗长的工具调用输出。
- ✅ **可配置压缩风格**: 可在更省 token、默认平衡和高保真摘要之间切换。
- ✅ **实时监控**: 实时监控上下文使用情况，超过 90% 发出警告。
- ✅ **快速预估 + 精确回退**: 提供更快的多语言 Token 预估，并在必要时回退到精确统计，便于调试。
- ✅ **智能模型匹配**: 自定义模型自动继承基础模型的阈值配置。
- ⚠ **多模态支持**: 图片内容会被保留，但其 Token **不参与计算**。请相应调整阈值。

---

## 这次解决了什么问题（通俗版）

- **问题：系统消息被摘要或丢失。**
  以前，过滤器可能会将被引用或后期注入的系统消息包含在摘要区域内，导致重要的指令丢失。现在，所有系统消息都严格按原样保留，永不被摘要。
- **问题：`keep_first` 逻辑不符合预期。**
  以前 `keep_first` 只是简单提取前 N 条消息。如果前几条全是系统消息，初始的问答（通常对上下文很重要）就会被压缩掉。现在 `keep_first` 确保保护 N 条非系统消息。
- **问题 1：引用别的聊天时，摘要失败可能把当前对话一起弄挂。**
  以前如果过滤器需要先帮被引用聊天做摘要，而这一步的 LLM 调用失败了，当前请求也可能直接失败。现在改成了“能摘要就摘要，失败就退回直接塞上下文”，当前对话不会被一起拖死。
- **问题 2：有些被引用聊天被截得太早，信息丢得太多。**
  以前有一段逻辑把 `max_summary_tokens` 这种“输出长度限制”误当成了“输入上下文窗口”，结果大一点的引用聊天会被过早截断。现在改成按摘要模型真实的输入窗口来算，能保留更多有用内容。
- **问题 3：后台摘要失败时，用户不容易知道发生了什么。**
  以前在 `show_debug_log=false` 时，有些后台失败只会留在内部日志里。现在关键失败会强制打到浏览器控制台，并在聊天状态里提醒去看 `F12`。

---

## 工作流总览

该过滤器分为两个阶段：

1. `inlet`：在请求发送给模型前执行，负责注入已有摘要、处理外部聊天引用、并在必要时裁剪上下文。
2. `outlet`：在模型回复完成后异步执行，负责判断是否需要生成新摘要，并在合适时写入数据库。

```mermaid
flowchart TD
    A[请求进入 inlet] --> B[规范化工具 ID 并按需裁剪超长工具输出]
    B --> C{是否附带引用聊天?}
    C -- 否 --> D[如果有当前聊天摘要就先加载]
    C -- 是 --> E[逐个检查被引用聊天]

    E --> F{已有完整 branch-valid 缓存摘要?}
    F -- 是 --> G[直接复用缓存摘要]
    F -- 否 --> H{有 partial valid 前缀摘要?}
    H -- 是 --> I[构造摘要 + active-branch tail]
    I --> I2{mixed reference 能直接放进预算?}
    I2 -- 是 --> I3[注入 mixed reference block]
    I2 -- 否 --> J[准备 continuation summary 输入]
    H -- 否 --> K{完整引用聊天能直接放进预算?}
    K -- 是 --> K2[直接注入完整引用聊天文本]
    K -- 否 --> J

    J --> L{引用聊天摘要调用成功?}
    L -- 是 --> L2[注入并持久化生成后的引用摘要]
    L -- 否 --> M[回退为直接注入上下文]

    G --> D
    I3 --> D
    K2 --> D
    L2 --> D
    M --> D

    D --> N[为当前聊天构造 Head + 已验证 Summary + Tail]
    N --> O{是否超过 max_context_tokens?}
    O -- 是 --> P[从最旧 atomic groups 开始裁剪]
    O -- 否 --> Q[把最终上下文发给模型]
    P --> Q

    Q --> R[模型返回当前回复]
    R --> S[Outlet 重建完整历史]
    S --> T{达到压缩阈值了吗?}
    T -- 否 --> U[结束]
    T -- 是 --> V[把摘要输入压到摘要模型可接受的上下文窗口]

    V --> W{后台摘要调用成功?}
    W -- 是 --> X[保存新摘要并更新状态]
    W -- 否 --> Y[强制输出浏览器控制台错误并提示用户查看]
```

### 关键说明

- `inlet` 只负责注入和裁剪上下文，不负责生成当前聊天的主摘要。
- `outlet` 异步生成摘要，不会阻塞当前回复。
- 外部聊天引用使用被引用聊天保存的 active branch（`history.currentId`）。引用附件本身不能选择另一条分支。
- 外部聊天引用可以来自已有完整 branch-valid 持久化摘要、partial branch-valid 摘要加未覆盖 active-branch tail、小聊天的完整文本，或动态生成/截断后的引用摘要。
- `chat_summary` 保存带 message refs 的 branch-valid 摘要行。旧的 count-only `chat_summary` schema 缺少可安全复用的覆盖范围元数据，启动时会被重建。
- 如果引用聊天基于已有缓存摘要加原文 tail 生成了 continuation summary，会写回被引用聊天自己的 `chat_summary` 覆盖范围，后续引用可直接复用。
- 如果引用聊天摘要失败，会自动回退为直接注入上下文，而不是让当前请求失败。
- 会保留所有 branch-valid 历史摘要行；用户在任意更早位置分叉后，下次压缩会复用当前分支上最接近的祖先摘要。
- `summary_model_max_context` 控制摘要输入窗口；`max_summary_tokens` 只控制生成摘要的输出长度，并且必须严格小于摘要模型输入窗口的 80%。这 20% 预留空间用于保证后续再次压缩时，可以把旧摘要和至少一部分新消息一起送入摘要模型；如果旧摘要自己就能占满整个输入窗口，再次压缩就无法有效推进。不满足要求会报配置错误，过滤器不会静默改小该值。
- 重要的后台摘要失败会显示到浏览器控制台 (`F12`) 和聊天状态提示里。
- 外部引用消息在裁剪阶段会被特殊保护，避免被最先删除。

---

## 安装与配置

### 1. 数据库（自动）

- 自动使用 Open WebUI 的共享数据库连接，**无需额外配置**。
- 首次运行自动创建 branch-aware `chat_summary` 表。旧版 count-only `chat_summary` 表，或仍通过 `chat_id` unique 限制每个 chat 只能一行的表，会被重建，后续重新生成安全摘要。如果插件无法反射检查现有 schema，会保留表不动并禁用摘要持久化，不会执行破坏性 DDL。

### 2. 过滤器顺序

- 建议顺序：前置过滤器（<10）→ 本过滤器（10）→ 后置过滤器（>10）。

---

## 配置参数

您可以在过滤器的设置中调整以下参数：

### 核心参数

| 参数                           | 默认值   | 描述                                                                                  |
| :----------------------------- | :------- | :------------------------------------------------------------------------------------ |
| `priority`                     | `10`     | 过滤器执行顺序，数值越小越先执行。                                                    |
| `compression_threshold_tokens` | `64000`  | **重要**: 当上下文总 Token 超过此值时后台生成摘要，建议设为模型上下文窗口的 50%-70%。 |
| `max_context_tokens`           | `128000` | **重要**: 上下文硬上限，超过即移除最早消息（保留受保护消息）。                        |
| `keep_first`                   | `0`      | 始终保留对话开始的 N 条**非系统消息**（以及它们之前的所有系统提示词）。               |
| `keep_last`                    | `6`      | 始终保留对话末尾的 N 条消息，确保最近上下文连贯。                                     |

### 摘要生成配置

| 参数                  | 默认值  | 描述                                                                                                                                        |
| :-------------------- | :------ | :------------------------------------------------------------------------------------------------------------------------------------------ |
| `summary_model`       | `None`  | 用于生成摘要的模型 ID。**强烈建议**配置快速、经济、上下文窗口大的模型（如 `gemini-2.5-flash`、`deepseek-v3`）。留空则尝试复用当前对话模型。 |
| `summary_model_max_context` | `0`     | 摘要请求可使用的输入上下文窗口。如果为 0，则回退到 `model_thresholds` 或全局 `max_context_tokens`。                                          |
| `max_summary_tokens`  | `16384` | 生成摘要时允许的最大输出 Token 数。它不是摘要输入窗口上限，并且必须严格小于有效摘要输入窗口（`summary_model_max_context`，或从 `model_thresholds` / `max_context_tokens` 回退得到的窗口）的 80%。剩余窗口用于下次压缩时同时容纳旧摘要和新消息；不满足要求会报错，不会自动调整。 |
| `summary_temperature` | `0.1`   | 控制摘要生成的随机性，较低的值结果更稳定。                                                                                                  |
| `summary_fail_mode`   | `silent` | 控制摘要 LLM 调用失败时的行为。`silent` 会记录错误并跳过本轮摘要；`raise` 会保留之前的硬抛错行为。                                         |
| `compression_style`   | `balanced` | 控制摘要压缩风格。`aggressive` 更省 token，`balanced` 在紧凑和保真之间取中间值，`faithful` 会尽量保留更多细节、论证和上下文层次。 |

### 高级配置

#### `model_thresholds` (模型特定阈值)

这是一个字典配置，可为特定模型 ID 覆盖全局 `compression_threshold_tokens` 与 `max_context_tokens`，适用于混合不同上下文窗口的模型。

**默认包含 GPT-4、Claude 3.5、Gemini 1.5/2.0、Qwen 2.5/3、DeepSeek V3 等推荐阈值。**

**配置示例：**

```json
{
  "gpt-4": {
    "compression_threshold_tokens": 8000,
    "max_context_tokens": 32000
  },
  "gemini-2.5-flash": {
    "compression_threshold_tokens": 734000,
    "max_context_tokens": 1048576
  }
}
```

| 参数                           | 默认值   | 描述                                                                                                                                    |
| :----------------------------- | :------- | :-------------------------------------------------------------------------------------------------------------------------------------- |
| `enable_tool_output_trimming`  | `true`   | 启用后（仅在 `function_calling: "native"` 下生效）会裁剪过大的本机工具输出，保留工具调用链结构并以简短占位替换冗长内容。             |
| `tool_trim_threshold_chars`     | `600`    | 当本机工具输出累计字符数达到该值时触发裁剪，适用于包含长文本或表格的工具结果。                                                           |
| `debug_mode`                   | `false`   | 是否在 Open WebUI 的控制台日志中打印详细的调试信息。生产环境默认且建议设为 `false`。 |
| `show_debug_log`               | `false`  | 是否在浏览器控制台 (F12) 打印调试日志。便于前端调试。                                                                   |
| `show_token_usage_status`      | `true`   | 是否在对话结束时显示 Token 使用情况的状态通知。                                                                         |
| `token_usage_status_threshold` | `80`     | 触发显示上下文用量状态通知的最低百分比阈值 (0-100)。                                                                    |

---

## ⭐ 支持

如果这个插件对你有帮助，欢迎到 [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions) 点个 Star，这将是我持续改进的动力，感谢支持。

## 故障排除 (Troubleshooting) ❓

- **初始系统提示丢失**：将 `keep_first` 设置为大于 0。
- **压缩效果不明显**：提高 `compression_threshold_tokens`，或降低 `keep_first` / `keep_last` 以增强压缩力度。
- **引用聊天摘要失败**：当前请求现在应该会继续执行，并回退为直接注入上下文。如果要看上游失败原因，请打开浏览器控制台 (`F12`)。
- **后台摘要看起来“没反应”**：重要失败现在会同时出现在状态提示和浏览器控制台 (`F12`) 中。
- **LLM 调用成功后仍出现 `Summary generation returned empty result`**：请更新或重新安装过滤器，确保数据库里保存的 function 内容已经是 v1.6.4 或更新版本。这个版本可以解析多种 provider 响应结构，但会刻意忽略 reasoning-only 输出；如果模型只返回 `reasoning_content` / `thinking` 而没有最终答案文本，浏览器控制台会显示响应结构，插件不会把思考过程保存为记忆。
- **摘要过短或过长**：调整 `compression_style`。如果追求最大 token 节省，使用 `aggressive`；如果希望维持默认折中，使用 `balanced`；如果更重视推理脉络、评估标准和候选方案，使用 `faithful`。
- **提交 Issue**: 如果遇到任何问题，请在 GitHub 上提交 Issue：[OpenWebUI Extensions Issues](https://github.com/Fu-Jie/openwebui-extensions/issues)

## 更新日志

请查看 [`v1.7.1` 版本发布说明](https://github.com/Fu-Jie/openwebui-extensions/blob/main/plugins/filters/async-context-compression/v1.7.1_CN.md) 获取本次版本的独立发布摘要。

完整历史请查看 GitHub 项目： [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions)
