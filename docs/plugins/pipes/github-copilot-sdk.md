# GitHub Copilot SDK Pipe for OpenWebUI

| By [Fu-Jie](https://github.com/Fu-Jie) · v0.13.3 | [⭐ Star this repo](https://github.com/Fu-Jie/openwebui-extensions) |
| :--- | ---: |

| ![followers](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_followers.json&label=%F0%9F%91%A5&style=flat) | ![points](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_points.json&label=%E2%AD%90&style=flat) | ![top](https://img.shields.io/badge/%F0%9F%8F%86-Top%20%3C1%25-10b981?style=flat) | ![contributions](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_contributions.json&label=%F0%9F%93%A6&style=flat) | ![downloads](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_downloads.json&label=%E2%AC%87%EF%B8%8F&style=flat) | ![saves](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_saves.json&label=%F0%9F%92%BE&style=flat) | ![views](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_views.json&label=%F0%9F%91%81%EF%B8%8F&style=flat) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |

This is a powerful **GitHub Copilot SDK** Pipe for **OpenWebUI** that provides a unified **Agentic experience**. It goes beyond simple model access by enabling autonomous **Intent Recognition**, **Web Search**, and **Context Compaction**. It seamlessly reuses your existing **Tools, MCP servers, OpenAPI servers, and Skills** from OpenWebUI to create a truly integrated ecosystem.

- **🧠 Autonomous Intent Recognition**: The Agent independently analyzes user goals to determine the most effective path forward.
- **🌐 Smart Web Search**: Built-in capability to trigger web searches autonomously based on task requirements.
- **♾️ Infinite Session (Context Compaction)**: Automatically manages long-running conversations by compacting context (summarization + TODO persistence) to maintain project focus.
- **🧩 Ecosystem Injection**: Directly reads and leverages your configured **OpenWebUI Tools, MCPs, OpenAPI Servers, and Skills**.
- **🎨 Interactive Delivery**: Native support for **HTML Artifacts** and **RichUI** components for real-time visualization and reporting.

> [!IMPORTANT]
> **Essential Companion**
> To unlock file handling and data analysis capabilities, you must install the [GitHub Copilot SDK Files Filter](https://openwebui.com/posts/403a62ee-a596-45e7-be65-fab9cc249dd6).

> [!TIP]
> **No Subscription Required for BYOK**
> If you are using your own API keys (BYOK mode with OpenAI/Anthropic), **you do NOT need a GitHub Copilot subscription.** A subscription is only required to access GitHub's official models.

---

---

## Install with Batch Install Plugins

If you already use [Batch Install Plugins from GitHub](https://openwebui.com/posts/batch_install_plugins_install_popular_plugins_in_s_c9fd6e80) , you can install or update this plugin with:

```text
Install plugin from Fu-Jie/openwebui-extensions
```

When the selection dialog opens, search for this plugin, check it, and continue.

> [!IMPORTANT]
> If the official OpenWebUI Community version is already installed, remove it first. After that, Batch Install Plugins can keep this plugin updated in future runs.

## ✨ v0.13.3: SDK 1.0.2 API Migration

- **📦 github-copilot-sdk 1.0.2**: Migrated to the stable 1.0.2 release. Removed deprecated `SubprocessConfig` and `SessionConfig` wrappers — connection and session options are now passed as plain dicts directly to `CopilotClient` and `create_session`/`resume_session`.
- **🔄 API Renames**: `Mode` → `SessionMode`, `SessionModeSetParams` → `ModeSetRequest`, `get_messages()` → `get_events()`, `destroy()` → `disconnect()`, `config_dir` → `config_directory`.
- **🔌 Client Lifecycle**: `CopilotClient` no longer accepts `auto_start`; call `await client.start()` explicitly after construction.
- **📊 State Access**: Replaced `client.get_state()` with direct `client._state` attribute access (returns `Literal["disconnected", "connecting", "connected", "error"]`).

---

## 🚀 Quick Start (Read This First)

If you only want to know how to use this plugin, read these sections in order:

1. **Quick Start**
2. **How to Use**
3. **Core Configuration**

Everything else is optional or advanced.

1. **Install the Pipe**
   - **Recommended**: Use **Batch Install Plugins** and select this plugin.
   - **Manual**: OpenWebUI -> **Workspace** -> **Functions** -> create a new function -> paste `github_copilot_sdk.py`.
2. **Install the Companion Files Filter** if you want uploaded files to reach the Pipe as raw files.
3. **Configure one credential path**
   - `GH_TOKEN` for official GitHub Copilot models
   - or `BYOK_API_KEY` for OpenAI / Anthropic
4. **Start a new chat and use it normally**
   - Select this Pipe's model
   - Ask your task in plain language
   - Upload files when needed

## 🧭 How to Use

You usually **do not** need to mention tools, skills, internal parameters, or RichUI syntax. Just describe the task naturally.

| Scenario | What you do | Example |
| :--- | :--- | :--- |
| Daily coding / debugging | Ask normally in chat | `Fix the failing tests and explain the root cause.` |
| File analysis | Upload files and ask normally | `Summarize this Excel file and chart the monthly trend.` |
| Long tasks | Ask for the outcome; the Pipe handles planning, status, and TODO tracking automatically | `Refactor this plugin and keep the docs in sync.` |
| HTML reports / dashboards | Ask the agent to generate a report or dashboard | `Create an interactive architecture overview for this repo.` |

> [!TIP]
> Ordinary users only need to remember one rule: if you ask for an interactive HTML result, the Pipe will usually use **RichUI** automatically. Only mention **artifacts** when you explicitly want artifacts-style output.

## 💡 What RichUI actually means

**RichUI = the generated HTML page is rendered directly inside the chat window.**

You can think of it as **a small interactive page inside the conversation**.

- If the agent generates a dashboard, report, timeline, architecture page, or explainer page, you may see RichUI.
- If you are just asking normal coding questions, debugging, writing, or file analysis tasks, you can ignore RichUI completely.
- You do **not** need to write XML, HTML tags, or special RichUI attributes. Just describe the result you want.

| What you ask for | What happens |
| :--- | :--- |
| `Fix this failing test` | Normal chat response. RichUI is not important here. |
| `Create an interactive dashboard for this repo` | RichUI is used by default. |
| `Generate this as artifacts` | Artifacts mode is used instead of RichUI. |
| `Build a project summary page if that helps explain it better` | The agent decides whether a page is useful. |

## ✨ Key Capabilities

- **🔑 Unified Intelligence (Official + BYOK)**: Seamlessly switch between official GitHub Copilot models and your own models (OpenAI, Anthropic, DeepSeek, xAI) via **Bring Your Own Key** mode.
- **🛡️ Physical Workspace Isolation**: Every session runs in its own isolated directory sandbox. This ensures absolute data privacy and prevents cross-chat file contamination while allowing the Agent full filesystem access.
- **🔌 Universal Tool Protocol**:
  - **Native MCP**: Direct, high-performance connection to Model Context Protocol servers.
  - **OpenAPI Bridge**: Connect to any external REST API as an Agent tool.
  - **OpenWebUI Native**: Zero-config bridge to your existing OpenWebUI tools and built-ins (Web Search, Memory, etc.).
- **🧩 OpenWebUI Skills Bridge**: Transforms simple OpenWebUI Markdown instructions into powerful SDK skill folders complete with supporting scripts, templates, and data.
- **🧭 Adaptive Planning and Execution**: The Agent decides whether to respond with a planning-first analysis or direct implementation flow based on task complexity, ambiguity, and user intent.
- **♾️ Infinite Session Management**: Advanced context window management with automatic "Compaction" (summarization + list persistence). Carry out weeks-long projects without losing the core thread.
- **📊 Interactive Artifacts & Publishing**:
  - **Live HTML/JS**: Instantly render and interact with apps, dashboards, or reports generated by the Agent.
  - **Persistent Publishing**: Agents can "publish" generated files (Excel, CSV, docs) to OpenWebUI's file storage, providing permanent download links.
- **🌊 UX-First Streaming**: Full support for "Thinking" processes (Chain of Thought), status indicators, and real-time progress bars for long-running tasks.
- **🧠 Deep Database Integration**: Real-time persistence of TODO lists and session metadata ensures your workflow state is always visible in the UI.

> [!TIP]
> **💡 Visualization Pro-Tip**
> To get the most out of **HTML Artifacts** and **RichUI**, we highly recommend asking the Agent to install the skill via its GitHub URL:
> "Install this skill: <https://github.com/nicobailon/visual-explainer>".
> This skill is specifically optimized for generating high-quality visual components and integrates perfectly with this Pipe.

### 🎛️ How RichUI works in normal use

For normal users, the rule is simple:

1. Ask for the result you want.
2. The AI decides whether a normal chat reply is enough.
3. If a page or dashboard would explain things better, the AI creates it automatically and shows it in chat.

You do **not** need to write XML tags, HTML snippets, or RichUI attributes yourself.

Examples:

- `Explain this repository structure.`
- `If useful, present this as an interactive architecture page.`
- `Turn this CSV into a simple dashboard.`

> [!TIP]
> Only mention **artifacts** when you explicitly want artifacts-style output. Otherwise, let the AI choose the best presentation automatically.

---

## 🧩 Companion Files Filter (Required for raw files)

`GitHub Copilot SDK Files Filter` is the companion plugin that prevents OpenWebUI's default RAG pre-processing from consuming uploaded files before the Pipe receives them.

- **What it does**: Moves uploaded files to `copilot_files` so the Pipe can access raw binaries directly.
- **Why it matters**: Without it, uploaded files may be parsed/vectorized early and the Agent may lose direct raw-file access.
- **v0.1.3 highlights**:
  - BYOK model-id matching fix (supports `github_copilot_official_sdk_pipe.xxx` prefixes).
  - Optional dual-channel debug log (`show_debug_log`) to backend logger + browser console.

---

## ⚙️ Core Configuration (Valves)

### 1. Administrator Settings (Base)

Administrators define the default behavior for all users in the function settings.

| Valve | Default | Description |
| :--- | :--- | :--- |
| `GH_TOKEN` | `""` | Global GitHub Token (Requires 'Copilot Requests' permission). |
| `COPILOTSDK_CONFIG_DIR` | `""` | Persistent directory for SDK config and session state (e.g., `/app/backend/data/.copilot`). |
| `ENABLE_OPENWEBUI_TOOLS` | `True` | Enable OpenWebUI Tools (includes defined Tools and Built-in Tools). |
| `ENABLE_OPENAPI_SERVER` | `True` | Enable OpenAPI Tool Server connection. |
| `ENABLE_MCP_SERVER` | `True` | Enable Direct MCP Client connection (Recommended). |
| `ENABLE_OPENWEBUI_SKILLS` | `True` | Enable bidirectional sync with OpenWebUI Workspace > Skills. |
| `OPENWEBUI_SKILLS_SHARED_DIR` | `/app/backend/data/cache/copilot-openwebui-skills` | Shared cache directory for skills. |
| `DISABLED_SKILLS` | `""` | Comma-separated skill names to disable in SDK session. |
| `REASONING_EFFORT` | `medium` | Reasoning effort level: low, medium, high. |
| `SHOW_THINKING` | `True` | Show model reasoning/thinking process. |
| `INFINITE_SESSION` | `True` | Enable Infinite Sessions (automatic context compaction). |
| `MAX_MULTIPLIER` | `1.0` | Max allowed billing multiplier (0x for free models only). |
| `EXCLUDE_KEYWORDS` | `""` | Exclude models containing these keywords (comma separated). |
| `TIMEOUT` | `300` | Timeout for each stream chunk (seconds). |
| `BYOK_TYPE` | `openai` | BYOK Provider Type: `openai`, `anthropic`. |
| `BYOK_BASE_URL` | `""` | BYOK Base URL (e.g., <https://api.openai.com/v1>). |
| `BYOK_MODELS` | `""` | BYOK Model List (comma separated). Leave empty to fetch from API. |
| `CUSTOM_ENV_VARS` | `""` | Custom environment variables (JSON format). |
| `DEBUG` | `False` | Enable this to see detailed logs in your browser console. |

### 2. User Settings (Individual Overrides)

Standard users can override these settings in their individual Profile/Function settings.

| Valve | Description |
| :--- | :--- |
| `GH_TOKEN` | Use your personal GitHub Token. |
| `REASONING_EFFORT` | Individual reasoning effort preference. |
| `SHOW_THINKING` | Show model reasoning/thinking process. |
| `MAX_MULTIPLIER` | Maximum allowed billing multiplier override. |
| `EXCLUDE_KEYWORDS` | Exclude models containing these keywords. |
| `ENABLE_OPENWEBUI_SKILLS` | Enable loading all active OpenWebUI skills readable by you into SDK `SKILL.md` directories. |
| `DISABLED_SKILLS` | Comma-separated skill names to disable for your own session. |
| `BYOK_API_KEY` | Use your personal OpenAI/Anthropic API Key. |

---

### 📤 HTML result behavior (advanced)

You can skip this section unless you are directly using `publish_file_from_workspace(...)`.

In plain language:

- `richui` = show the generated HTML directly inside the chat
- `artifacts` = use artifacts-style HTML delivery when you explicitly want that style

Internally, this behavior is controlled by the `embed_type` parameter of `publish_file_from_workspace(...)`.

- **Rich UI mode (`richui`, default for HTML)**: The agent returns `[Preview]` + `[Download]` only. OpenWebUI renders the interactive preview automatically after the message.
- **Artifacts mode (`artifacts`)**: Use this only when you explicitly want artifacts-style HTML delivery.
- **📄 PDF safety rule**: Always return Markdown links only (`[Preview]` / `[Download]` when available). Do not embed PDFs with iframe or HTML blocks.
- **⚡ Stable dual-channel publishing**: Keeps interactive viewing and persistent file download aligned across local and object-storage backends.
- **✅ Status integration**: Emits publishing progress and completion feedback to the OpenWebUI status bar.
- **📘 Publishing Tool Guide (GitHub)**: [publish_file_from_workspace Guide](https://github.com/Fu-Jie/openwebui-extensions/blob/main/plugins/pipes/github-copilot-sdk/PUBLISH_FILE_FROM_WORKSPACE.md)

> [!TIP]
> Most users do not need to set `embed_type` manually. Ask for a report or dashboard normally. Only say `use artifacts` when you specifically want artifacts-style presentation. If you are not calling `publish_file_from_workspace(...)` yourself, you can usually ignore this parameter.

---

### 🧩 OpenWebUI Skills Bridge & `manage_skills` Tool

The SDK now features a bidirectional bridge with the OpenWebUI **Workspace > Skills** page:

- **🔄 Automatic Sync**: Skills created or updated in the OpenWebUI UI are automatically downloaded as `SKILL.md` folders into the SDK's shared cache on every request.
- **🛠️ `manage_skills` Tool**: The Agent can deterministically manage skills using this tool.
  - `list`: List all installed skills and their descriptions.
  - `install`: Install a skill from a GitHub URL (auto-normalized to archive link) or a direct `.zip`/`.tar.gz`.
  - `create`: Create a new skill directory from context, writing `SKILL.md` and any extra resource files (scripts, templates).
  - `edit`: Update an existing skill folder.
  - `delete`: Atomically delete both the local directory and the linked OpenWebUI DB entry.
- **📁 Full Folder Support**: Unlike the single-markdown storage in OpenWebUI DB, the SDK loads the **entire folder** for each skill. This allows skills to carry binary scripts, data files, or complex templates alongside the core instructions.
- **🌐 Shared Persistent Cache**: Skills are stored in `OPENWEBUI_SKILLS_SHARED_DIR/shared/`, which is persistent across sessions and container restarts.
- **📚 Full Skill Docs (GitHub)**: [manage_skills Tool Guide](https://github.com/Fu-Jie/openwebui-extensions/blob/main/plugins/pipes/github-copilot-sdk/SKILLS_MANAGER.md) | [Skills Best Practices](https://github.com/Fu-Jie/openwebui-extensions/blob/main/plugins/pipes/github-copilot-sdk/SKILLS_BEST_PRACTICES.md)

---

### 🌊 Fluid UX & Granular Status Feedback

Say goodbye to the "stuck" feeling during complex processing:

- **🔄 Real-Time Status Bubbles**: Maps internal SDK events (`turn_start`, `compaction`, `subagent_started`) directly to the OpenWebUI status bar.
- **🧭 Richer Stage Descriptions**: Status text now explicitly reflects phases such as processing, skill invocation, tool execution, tool completion/failure, publishing, and final completion.
- **⏱️ Long-Task Heartbeat**: During long waits, the status bar emits periodic "still processing" updates (elapsed-time style) to avoid silent stalls.
- **📈 Tool Progress Tracking**: Long-running tool executions provide live progress percentages and descriptive sub-task updates in the status bar.
- **⚡ Immediate Feedback**: Response starts with an instant "Assistant is processing" status, eliminating idle wait time before the first token.

---

### 🛡️ Smart Version Compatibility

The plugin automatically adapts its feature set based on your OpenWebUI version:

- **v0.8.0+**: Rich UI, live status bubbles, and integrated HTML preview.
- **Older**: Automatic fallback to standard Markdown blocks for maximum stability.

---

## 🎯 Use Cases (What can you do?)

- **📁 Fully Autonomous DevOps**: Agent analyzes code, runs tests, and applies patches within its isolated sandbox.
- **📊 Deep Data Auditing**: Directly process raw Excel/CSV data via Python (bypassing RAG) and generate visual reports.
- **📝 Long-Task Management**: Automatically decomposes complex requests and persists TOD·O progress across sessions.

---

## ⭐ Support

If this plugin has been useful, a **Star** on [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions) would be a great motivation for me. Thank you!

---

## 🚀 Installation & Configuration

### 1) Import Function

1. Open OpenWebUI, go to **Workspace** -> **Functions**.
2. Click **+** (Create Function), paste the content of `github_copilot_sdk.py`.
3. Save and ensure it is enabled.

### 2) Get Token

1. Visit [GitHub Token Settings](https://github.com/settings/tokens?type=beta).
2. Create **Fine-grained token**, granting **Account permissions** -> **Copilot Requests** access.
3. Paste the generated Token into the `GH_TOKEN` field in Valves.

### 3) Authentication Requirement (Mandatory)

You MUST configure **at least one** credential source:

- `GH_TOKEN` (GitHub Copilot subscription route), or
- `BYOK_API_KEY` (OpenAI/Anthropic route).

If neither is configured, the model list will not appear.

---

## 📋 Troubleshooting & Dependencies

- **Agent ignores files?**: Ensure the Files Filter is enabled, otherwise RAG will interfere with raw binaries.
- **No status updates?**: Status bubbles are emitted for processing/tool phases; TODO progress bars specifically appear when the Agent uses `update_todo`.
- **Dependencies**: This Pipe automatically manages `github-copilot-sdk` (Python) and utilizes the bundled binary CLI. No manual install required.

---

## Changelog

See the full history on GitHub: [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions)
