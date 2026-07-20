# GitHub Copilot Agent SDK Pipe

| 作者：[Fu-Jie](https://github.com/Fu-Jie) · v0.13.3 | [⭐ 点个 Star 支持项目](https://github.com/Fu-Jie/openwebui-extensions) |
| :--- | ---: |

| ![followers](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_followers.json&label=%F0%9F%91%A5&style=flat) | ![points](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_points.json&label=%E2%AD%90&style=flat) | ![top](https://img.shields.io/badge/%F0%9F%8F%86-Top%20%3C1%25-10b981?style=flat) | ![contributions](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_contributions.json&label=%F0%9F%93%A6&style=flat) | ![downloads](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_downloads.json&label=%E2%AC%87%EF%B8%8F&style=flat) | ![saves](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_saves.json&label=%F0%9F%92%BE&style=flat) | ![views](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_views.json&label=%F0%9F%91%81%EF%B8%8F&style=flat) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |

这是一个将 **GitHub Copilot SDK** 集成到 **OpenWebUI** 的 Agent SDK 管道，支持 **Agent Team** 多智能体协作、**Session Mode**（`autopilot`/`interactive`/`plan`）、**网页搜索**、**上下文压缩**，并复用 OpenWebUI 的 **Tools、MCP 服务器和 Skills**。

> [!IMPORTANT]
> **核心伴侣组件**
> 如需让 Copilot 直接处理上传文件（绕过 OpenWebUI 默认的 RAG 文件解析），请安装 [GitHub Copilot SDK Files Filter](https://openwebui.com/posts/403a62ee-a596-45e7-be65-fab9cc249dd6)。

> [!TIP]
> **BYOK 模式无需订阅**
> 如果您使用自带的 API Key (BYOK 模式对接 OpenAI/Anthropic)，**您不需要 GitHub Copilot 官方订阅**。只有在访问 GitHub 官方模型时才需要订阅。

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

> [!IMPORTANT]
> **如果插件在更新后报错，请重启 OpenWebUI 服务器。** 插件代码会被缓存在内存中，旧字节码可能导致 import 错误，重启可以清除缓存并加载新版本。

---

## 🚀 快速上手

1. **通过 Batch Install Plugins 安装** → 选择本插件
2. **配置凭证**：`GH_TOKEN`（GitHub Copilot）或 `BYOK_API_KEY`（OpenAI/Anthropic）
3. **开始对话** — 选择本 Pipe 的模型，正常提需求即可

> Files Filter 让 Copilot 直接处理上传文件（绕过 OpenWebUI 默认的 RAG 解析）。安装：[点击安装](https://openwebui.com/posts/403a62ee-a596-45e7-be65-fab9cc249dd6)

## 🧭 日常怎么用

直接说出你想要的结果即可，不需要提工具或参数。

| 你怎么说 | 系统怎么做 |
| :--- | :--- |
| `修复失败的测试` | 正常回复 |
| `总结这个 Excel 并画趋势图` | Agent 处理文件并生成图表 |
| `创建一个交互式看板` | RichUI 页面直接渲染在聊天里 |
| `重构这个插件` | Agent 规划、执行并自动跟踪 TODO |

## ✨ 核心能力

| 能力 | 对你意味着什么 |
| :--- | :--- |
| 🤖 **Agentic AI** | Agent 自主规划达成目标的路径 |
| 👥 **Agent Team** | 在一个会话中协调多个子 Agent — 指定领导者、共享工具 |
| 🔄 **Session Mode** | 选择 `autopilot`（自主执行）、`interactive`（逐步确认）或 `plan`（计划优先） |
| 🛠️ **内置工具** | 文件系统、Git、bash、发布产物到工作区、基于目录的技能管理等核心工具，安装在 Docker 数据目录中，跨会话持久化 |
| 🌐 **网页搜索** | 当问题需要最新信息时自动触发搜索 |
| ♾️ **无限会话** | 数周长的项目也能自动压缩上下文保持跟踪 |
| 🧩 **Tools & MCP 桥接** | OpenWebUI 的 Tools 和 MCP 服务器自动可用 |
| 🎨 **RichUI / Artifacts** | 交互式看板和页面直接渲染在聊天里 |
| 🛡️ **工作区隔离** | 每个会话尽可能在独立环境中运行以保护隐私 |

---

## 🧩 Companion Files Filter

让 Copilot 直接处理上传文件（Excel、CSV、图片），绕过 OpenWebUI 默认的 RAG 解析。

安装：[GitHub Copilot SDK Files Filter](https://openwebui.com/posts/403a62ee-a596-45e7-be65-fab9cc249dd6)

---

## ⚙️ 核心配置 (Valves)

配置凭证（二选一或同时配置）：

| Valve | 配置内容 |
| :--- | :--- |
| `GH_TOKEN` | GitHub Copilot Token（见下方 [获取 Token](#获取-token)） |
| `BYOK_API_KEY` | OpenAI 或 Anthropic Key |
| `BYOK_TYPE` | BYOK 类型：`openai` 或 `anthropic` |
| `BYOK_BASE_URL` | BYOK API 端点（使用 BYOK 时必须设置），如 `https://api.openai.com/v1`（OpenAI）或 `https://api.anthropic.com`（Anthropic）。其他供应商可能不同，请查阅供应商文档。 |

> 💡 **同时配置**：可以同时配置 `GH_TOKEN` 和 `BYOK_API_KEY`，模型列表会同时显示两组模型。

其他参数可选。完整参数列表见 [详细教程](https://github.com/Fu-Jie/openwebui-extensions/blob/main/plugins/pipes/github-copilot-sdk/TUTORIAL_CN.md)。

### 获取 Token

1. 访问 [github.com/settings/tokens?type=beta](https://github.com/settings/tokens?type=beta)
2. 创建 **Fine-grained token**，勾选 **Account permissions → Copilot Requests**
3. 将 Token 粘贴到 `GH_TOKEN` 字段

---

## 🤝 支持

如果这个插件对你有帮助，欢迎到 [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions) 点个 Star，这将是我持续改进的动力，感谢支持。

---

## 故障排除

- **Agent 忽略上传的文件？** → 安装 Files Filter 让 Copilot 直接处理（见上方）
- **更新后报错？** → 重启 OpenWebUI 服务器清除缓存
