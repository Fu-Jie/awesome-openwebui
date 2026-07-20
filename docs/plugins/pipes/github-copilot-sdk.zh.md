# GitHub Copilot Official SDK Pipe

| 作者：[Fu-Jie](https://github.com/Fu-Jie) · v0.13.3 | [⭐ 点个 Star 支持项目](https://github.com/Fu-Jie/openwebui-extensions) |
| :--- | ---: |

| ![followers](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_followers.json&label=%F0%9F%91%A5&style=flat) | ![points](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_points.json&label=%E2%AD%90&style=flat) | ![top](https://img.shields.io/badge/%F0%9F%8F%86-Top%20%3C1%25-10b981?style=flat) | ![contributions](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_contributions.json&label=%F0%9F%93%A6&style=flat) | ![downloads](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_downloads.json&label=%E2%AC%87%EF%B8%8F&style=flat) | ![saves](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_saves.json&label=%F0%9F%92%BE&style=flat) | ![views](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_views.json&label=%F0%9F%91%81%EF%B8%8F&style=flat) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |

这是一个将 **GitHub Copilot SDK** 深度集成到 **OpenWebUI** 中的强大 Agent SDK 管道。它不仅实现了 SDK 的核心功能，还支持 **智能意图识别**、**自主网页搜索** 与 **自动上下文压缩**，并能够无缝读取 OpenWebUI 已有的配置进行智能注入，让 Agent 能够具备以下能力：

- **🧠 智能意图识别**：Agent 能自主分析用户任务的深层意图，决定最有效的处理路径。
- **🌐 自主网页搜索**：具备独立的网页搜索触发判断力，无需用户手动干预。
- **♾️ 自动压缩上下文**：支持 Infinite Session，自动对长对话进行上下文压缩与摘要，确保长期任务跟进。
- **🛠️ 全功能 Skill 体系**：完美支持本地自定义 Skill 目录，通过脚本与资源的结合实现真正的功能增强。
- **🧩 深度生态复用**：直接复用您在 OpenWebUI 中配置的各种 **工具 (Tools)**、**MCP**、**OpenAPI Server** 和 **技能 (Skills)**。

为您带来更强、更完整的交互体验。

> [!IMPORTANT]
> **核心伴侣组件**
> 如需启用文件处理与数据分析能力，请务必安装 [GitHub Copilot SDK Files Filter](https://openwebui.com/posts/403a62ee-a596-45e7-be65-fab9cc249dd6)。
> [!TIP]
> **BYOK 模式无需订阅**
> 如果您使用自带的 API Key (BYOK 模式对接 OpenAI/Anthropic)，**您不需要 GitHub Copilot 官方订阅**。只有在访问 GitHub 官方模型时才需要订阅。

---

---

## 使用 Batch Install Plugins 安装

如果你已经安装了 [Batch Install Plugins from GitHub](https://openwebui.com/posts/batch_install_plugins_install_popular_plugins_in_s_c9fd6e80) ，可以用下面这句来安装或更新当前插件：

```text
从 Fu-Jie/openwebui-extensions 安装插件
```

当选择弹窗打开后，搜索当前插件，勾选后继续安装即可。

> [!IMPORTANT]
> 如果你已经安装了 OpenWebUI 官方社区里的同名版本，请先删除旧版本，否则重新安装时可能报错。删除后，Batch Install Plugins 后续就可以继续负责更新这个插件。

## ✨ v0.13.3：SDK 1.0.2 API 迁移

- **📦 github-copilot-sdk 1.0.2**：迁移至稳定的 1.0.2 版本。移除了已弃用的 `SubprocessConfig` 和 `SessionConfig` 包装器——连接和会话选项现在以普通字典形式直接传递给 `CopilotClient` 和 `create_session`/`resume_session`。
- **🔄 API 重命名**：`Mode` → `SessionMode`、`SessionModeSetParams` → `ModeSetRequest`、`get_messages()` → `get_events()`、`destroy()` → `disconnect()`、`config_dir` → `config_directory`。
- **🔌 客户端生命周期**：`CopilotClient` 不再接受 `auto_start` 参数；构造后需显式调用 `await client.start()`。
- **📊 状态访问**：用直接属性 `client._state` 替代 `client.get_state()`（返回 `Literal["disconnected", "connecting", "connected", "error"]`）。

---

## 🚀 最短上手路径（先看这里）

如果你现在最关心的是“这个插件到底怎么用”，建议按这个顺序阅读：

1. **最短上手路径**
2. **日常怎么用**
3. **核心配置**

其他章节都属于补充说明或进阶内容。

1. **安装 Pipe**
   - **推荐**：使用 **Batch Install Plugins** 安装并勾选当前插件。
   - **手动**：OpenWebUI -> **Workspace** -> **Functions** -> 新建 Function -> 粘贴 `github_copilot_sdk.py`。
2. **如果你要处理上传文件**，再安装配套的 `GitHub Copilot SDK Files Filter`。
3. **至少配置一种凭据**
   - `GH_TOKEN`：使用 GitHub 官方 Copilot 模型
   - `BYOK_API_KEY`：使用 OpenAI / Anthropic 自带 Key
4. **新建对话后直接正常提需求**
   - 选择当前 Pipe 的模型
   - 像平时一样描述任务
   - 需要时上传文件

## 🧭 日常怎么用

大多数情况下，你**不需要**主动提 tools、skills、内部参数或 RichUI 语法，直接自然描述任务即可。

| 场景 | 你怎么做 | 示例 |
| :--- | :--- | :--- |
| 日常编码 / 排错 | 直接在聊天里提需求 | `修复失败的测试，并解释根因。` |
| 文件分析 | 上传文件后直接提需求 | `总结这个 Excel，并画出每月趋势图。` |
| 长任务 | 只要说出目标即可；Pipe 会自动处理规划、状态提示和 TODO 跟踪 | `重构这个插件，并同步更新文档。` |
| HTML 报告 / 看板 | 直接让 Agent 生成交互式报告或看板 | `帮我生成这个仓库的交互式架构总览。` |

> [!TIP]
> 普通用户只要记住一条：如果你让 Agent 生成交互式 HTML 结果，这个 Pipe 通常会自动使用 **RichUI**。只有当你明确想要 artifacts 风格时，才需要特别说明。

## 💡 RichUI 到底是什么意思？

**RichUI = Agent 生成的 HTML 页面，会直接显示在聊天窗口里。**

你可以把它理解为：**对话里面直接出现一个可交互的小网页 / 小看板**。

- 如果 Agent 生成的是看板、报告、时间线、架构图页面或说明型页面，你就可能会看到 RichUI。
- 如果你只是正常问代码问题、调试、写文档、分析文件，其实可以完全忽略 RichUI。
- 你**不需要**自己写 XML、HTML 标签或任何特殊 RichUI 属性，直接描述你想要的结果即可。

| 你怎么说 | 系统会怎么做 |
| :--- | :--- |
| `修复这个失败测试` | 正常聊天回复，这时 RichUI 基本不重要。 |
| `帮我生成一个交互式仓库看板` | 默认使用 RichUI。 |
| `请用 artifacts 形式生成` | 改用 artifacts，而不是 RichUI。 |
| `如果做成页面更清楚，就帮我做成页面` | AI 会自己判断页面是否更合适。 |

## ✨ 核心能力 (Key Capabilities)

- **🔑 统一智能体验 (官方 + BYOK)**: 自由切换官方模型与自定义服务商（OpenAI, Anthropic, DeepSeek, xAI），支持 **BYOK (自带 Key)** 模式。
- **🛡️ 物理级工作区隔离**: 每个会话在独立的沙箱目录中运行。确保绝对的数据隐私，防止不同聊天间的文件污染，同时给予 Agent 完整的文件系统操作权限。
- **🔌 通用工具协议**:
  - **原生 MCP**: 高性能直连 Model Context Protocol 服务器。
  - **OpenAPI 桥接**: 将任何外部 REST API 一键转换为 Agent 可调用的工具。
  - **OpenWebUI 原生桥接**: 零配置接入现有的 OpenWebUI 工具及内置功能（网页搜索、记忆等）。
- **🧩 OpenWebUI Skills 桥接**: 将简单的 OpenWebUI Markdown 指令转化为包含脚本、模板 and 数据的强大 SDK 技能文件夹。
- **🧭 自适应规划与执行**: Agent 会根据任务复杂度、歧义程度和用户意图，自主决定先输出结构化方案，还是直接分析、实现并验证。
- **♾️ 无限会话管理**: 先进的上下文窗口管理，支持自动“压缩”（摘要提取 + TODO 列表持久化）。支持长达数周的项目跟踪而不会丢失核心上下文。
- **📊 交互式产物与发布**:
  - **实时 HTML/JS**: 瞬间渲染并交互 Agent 生成的应用程序、可视化看板或报告。
  - **持久化发布**: Agent 可将生成的产物（Excel, CSV, 文档）发布至 OpenWebUI 文件存储，并在聊天中提供永久下载链接。
- **🌊 极致交互体验**: 完整支持深度思考过程 (Thinking Process) 流式渲染、状态指示器以及长任务实时进度条。
- **🧠 深度数据库集成**: TODO 列表与会话元数据的实时持久化，确保任务执行状态在 UI 上清晰可见。

> [!TIP]
> **💡 增强渲染建议**
> 为了获得最精美的 **HTML Artifacts** 与 **RichUI** 效果，建议在对话中通过提供的 GitHub 链接直接命令 Agent 安装：
> “请安装此技能：<https://github.com/nicobailon/visual-explainer”。>
> 该技能专为生成高质量可视化组件而设计，能够与本 Pipe 完美协作。

### 🎛️ RichUI 在日常使用里怎么理解

对普通用户来说，规则很简单：

1. 直接说出你想要的结果。
2. AI 会自己判断普通聊天回复是否已经足够。
3. 如果做成页面、看板或可视化会更清楚，AI 会自动生成并直接显示在聊天里。

你**不需要**自己写 XML 标签、HTML 片段或 RichUI 属性。

例如：

- `请解释这个仓库的结构。`
- `如果用交互式架构页更清楚，就做成页面。`
- `把这个 CSV 做成一个简单看板。`

> [!TIP]
> 只有当你明确想要 **artifacts 风格** 时，才需要特别说明。其他情况下，直接让 AI 自动选择最合适的展示方式即可。

---

## 🧩 配套 Files Filter（原始文件必备）

`GitHub Copilot SDK Files Filter` 是本 Pipe 的配套插件，用于阻止 OpenWebUI 默认 RAG 在 Pipe 接手前抢先处理上传文件。

- **作用**: 将上传文件移动到 `copilot_files`，让 Pipe 能直接读取原始二进制。
- **必要性**: 若未安装，文件可能被提前解析/向量化，Agent 可能拿不到原始文件。
- **v0.1.3 重点**:
  - 修复 BYOK 模型 ID 识别（支持 `github_copilot_official_sdk_pipe.xxx` 前缀匹配）。
  - 新增双通道调试日志（`show_debug_log`）：后端 logger + 浏览器控制台。

---

## ⚙️ 核心配置 (Valves)

### 1. 管理员设置（全局默认）

管理员可在函数设置中为所有用户定义默认行为。

| Valve | 默认值 | 描述 |
| :--- | :--- | :--- |
| `GH_TOKEN` | `""` | 全局 GitHub Fine-grained Token，需要 `Copilot Requests` 权限。 |
| `COPILOTSDK_CONFIG_DIR` | `/app/backend/data/.copilot` | SDK 配置与会话状态的持久化目录。 |
| `ENABLE_OPENWEBUI_TOOLS` | `True` | 启用 OpenWebUI Tools 与 Built-in Tools。 |
| `ENABLE_OPENAPI_SERVER` | `True` | 启用 OpenAPI Tool Server 连接。 |
| `ENABLE_MCP_SERVER` | `True` | 启用 MCP Server 连接。 |
| `ENABLE_OPENWEBUI_SKILLS` | `True` | 启用 OpenWebUI Skills 到 SDK 技能目录的同步。 |
| `OPENWEBUI_SKILLS_SHARED_DIR` | `/app/backend/data/cache/copilot-openwebui-skills` | Skills 共享缓存目录。 |
| `DISABLED_SKILLS` | `""` | 逗号分隔的禁用技能名列表。 |
| `REASONING_EFFORT` | `medium` | 推理强度：`low`、`medium`、`high`、`xhigh`。 |
| `SHOW_THINKING` | `True` | 是否显示思考过程。 |
| `INFINITE_SESSION` | `True` | 是否启用无限会话与上下文压缩。 |
| `MAX_MULTIPLIER` | `1.0` | 允许的最大账单倍率。`0` 表示仅允许免费模型。 |
| `EXCLUDE_KEYWORDS` | `""` | 排除包含这些关键词的模型。 |
| `TIMEOUT` | `300` | 每个流式分片的超时时间（秒）。 |
| `BYOK_TYPE` | `openai` | BYOK 提供商类型：`openai` 或 `anthropic`。 |
| `BYOK_BASE_URL` | `""` | BYOK Base URL。 |
| `BYOK_MODELS` | `""` | BYOK 模型列表，留空则尝试从 API 获取。 |
| `CUSTOM_ENV_VARS` | `""` | 自定义环境变量（JSON 格式）。 |
| `DEBUG` | `False` | 启用浏览器控制台/技术调试日志。 |

### 2. 用户设置（个人覆盖）

普通用户可在个人资料或函数设置中覆盖以下选项。

| Valve | 描述 |
| :--- | :--- |
| `GH_TOKEN` | 使用个人 GitHub Token。 |
| `REASONING_EFFORT` | 个人推理强度偏好。 |
| `SHOW_THINKING` | 是否显示思考过程。 |
| `MAX_MULTIPLIER` | 个人最大账单倍率限制。 |
| `EXCLUDE_KEYWORDS` | 个人模型排除关键词。 |
| `ENABLE_OPENWEBUI_TOOLS` | 是否启用 OpenWebUI Tools 与 Built-in Tools。 |
| `ENABLE_OPENAPI_SERVER` | 是否启用 OpenAPI Tool Server。 |
| `ENABLE_MCP_SERVER` | 是否启用 MCP Server。 |
| `ENABLE_OPENWEBUI_SKILLS` | 是否加载你可读的 OpenWebUI Skills 到 SDK 技能目录。 |
| `DISABLED_SKILLS` | 逗号分隔的个人禁用技能列表。 |
| `BYOK_API_KEY` | 个人 BYOK API Key。 |
| `BYOK_TYPE` | 个人 BYOK 提供商类型覆盖。 |
| `BYOK_BASE_URL` | 个人 BYOK Base URL 覆盖。 |
| `BYOK_BEARER_TOKEN` | 个人 BYOK Bearer Token 覆盖。 |
| `BYOK_MODELS` | 个人 BYOK 模型列表覆盖。 |
| `BYOK_WIRE_API` | 个人 BYOK Wire API 覆盖。 |

---

## 🚀 安装与配置

### 1. 导入函数

1. 打开 OpenWebUI，进入 **Workspace** -> **Functions**。
2. 点击 **+**（Create Function），粘贴 `github_copilot_sdk.py` 内容。
3. 保存并确保已启用。

### 2. 获取 Token

1. 访问 [GitHub Token Settings](https://github.com/settings/tokens?type=beta)。
2. 创建 **Fine-grained token**，授予 **Account permissions** -> **Copilot Requests** 权限。
3. 将生成的 Token 填入 `GH_TOKEN`。

### 3. 认证要求（必填其一）

必须至少配置一种凭据来源：

- `GH_TOKEN`（GitHub Copilot 官方订阅路线），或
- `BYOK_API_KEY`（OpenAI / Anthropic 自带 Key 路线）。

如果两者都未配置，模型列表将不会显示。

---

## 📤 HTML 结果展示方式（进阶）

如果你没有直接使用 `publish_file_from_workspace(...)`，这一节可以跳过。

先用一句人话解释：

- `richui` = 生成的 HTML 直接显示在聊天里
- `artifacts` = 你明确想要 artifacts 风格时使用的另一种 HTML 交付方式

在内部实现上，这个行为由 `publish_file_from_workspace(..., embed_type=...)` 控制。

- **RichUI 模式（`richui`，HTML 默认）**：Agent 只返回 `[Preview]` + `[Download]`，聊天结束后由 OpenWebUI 自动渲染交互预览。
- **Artifacts 模式（`artifacts`）**：只有在你明确想要 artifacts 风格展示时再使用。
- **PDF 安全规则**：PDF 只返回 Markdown 链接，不要用 iframe / HTML block 嵌入。
- **双通道发布**：同时兼顾对话内查看与持久下载。
- **状态提示**：发布过程会同步显示在 OpenWebUI 状态栏。

> [!TIP]
> 如果你只是日常使用这个 Pipe，通常不需要手动提 `embed_type`。直接说“生成一个交互式报告 / 看板”即可；只有你明确想要 artifacts 风格时再特别说明。如果你并没有直接调用 `publish_file_from_workspace(...)`，那通常可以忽略这个参数。

---

## 🤝 支持 (Support)

如果这个插件对你有帮助，欢迎到 [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions) 点个 Star，这将是我持续改进的动力，感谢支持。

---

## ⚠️ 故障排除 (Troubleshooting)

- **工具无法使用?** 请先确认 OpenWebUI Tools / MCP / OpenAPI Server 已在对应设置中启用。
- **文件找不到?** 确保已启用配套的 `Files Filter` 插件，否则 RAG 可能会提前消费原始文件。
- **BYOK 报错?** 确认 `BYOK_BASE_URL` 包含正确协议前缀（如 `https://`），且模型 ID 准确无误。
- **卡在 "Thinking..."?** 检查后端网络连接，或打开 `DEBUG` 查看更详细的 SDK 日志。

---

## Changelog

完整历史请查看 GitHub 项目主页：[OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions)
