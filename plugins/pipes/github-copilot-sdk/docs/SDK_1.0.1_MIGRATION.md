# GitHub Copilot SDK 0.2.2 → 1.0.1 API 迁移笔记

> **Verified on 2026-06-13** by @colin-chen, on Python 3.13.2 (arm64), SDK version 1.0.1
> 本文档是 4-PR 升级方案([PR 1](../..))的产出,后续 PR 2/3/4 直接引用本文档作为权威依据。
> 任何与本文档冲突的代码修改都必须先在 PR 中更新本文档。

## 0. 重大偏离(必读)

原计划假设 0.2.2 → 1.0.1 是"SubprocessConfig 字段重命名"的增量升级。**实测发现 1.0.1 的破坏性变更远大于预期**:

| 主题 | 原计划假设 | 实际发现 | 影响 |
|------|-----------|---------|------|
| `SubprocessConfig` | 仍存在,字段重命名 | **整个类被移除**,改用 `RuntimeConnection` 抽象 | **高** — 主插件 `_build_client_config` 需重写 |
| `CopilotClient.__init__` | 接受 `SubprocessConfig` 实例 | 接受 `connection: RuntimeConnection \| None`,且 **所有参数 keyword-only** | **高** — `CopilotClient(client_config, auto_start=True)` 这种位置参数会 `TypeError` |
| `Mode` 枚举 | 仍存在 | 改为 `SessionMode` enum(`interactive`/`plan`/`autopilot`) | 低 — 名字换一下 |
| `create_session` 的 `config_dir` | 未列 | 改名为 `config_directory` | 低 |
| 事件 payload 字段 | 假设基本兼容 | **多个关键字段重命名/消失**:`new_context` 整组没了、`tool.name` 改 `tool_name`、`progress` 改 `progress_message`、`partial_result` 改 `partial_output`、`subagent.*.name` 改 `agent_name` | **高** — 影响 16 个事件 handler |
| `session.destroy` | 存在,需 try/except | **完全移除**,只能 `disconnect` | 中 |
| `Session` 类 | 叫 `Session` | 改名为 `CopilotSession` | 低 |
| `MCP` `type` 字符串 | 不确定 | `MCPStdioServerConfig.type` 支持 `Literal['local', 'stdio']`;`MCPHTTPServerConfig.type` 支持 `Literal['http', 'sse']` | 低 — 需兼容新值 |

PR 3 的实际改动量比原计划 §2.1 列的 8 处多,需重新规划代码行数。

---

## 1. 包结构变化

### 1.1 顶层模块

| 0.2.2 | 1.0.1 | 备注 |
|-------|-------|------|
| `copilot.types` (公开) | **已移除** — `ModuleNotFoundError` | 原 `SubprocessConfig`/`SessionConfig`/`Tool` 等所有公开类型都移走 |
| `copilot.client` | `copilot.client` | `SubprocessConfig` 移到 client 模块 → 又被移除 |
| `copilot.jsonrpc` | `copilot._jsonrpc` (私有) | 前面加下划线 |
| `copilot.telemetry` | `copilot._telemetry` (私有) |  |
| (无) | `copilot._diagnostics`、`copilot._mode`、`copilot._sdk_protocol_version` | 新增私有模块 |
| (无) | `copilot.canvas`、`copilot.session_fs_provider`、`copilot.tools` | 新增公开模块 |
| `copilot.session` | `copilot.session` | 仍存在,但类名/字段都改了 |
| `copilot.generated.rpc` | `copilot.generated.rpc` | 仍存在,内容大量重写 |

### 1.2 关键模块存在性(实测 1.0.1)

| 模块 | 状态 |
|------|------|
| `copilot.types` | ❌ `ImportError` |
| `copilot.session` | ✅ |
| `copilot._jsonrpc` | ✅ |
| `copilot._telemetry` | ✅ |
| `copilot.generated.rpc` | ✅ |
| `copilot.generated.session_events` | ✅ |
| `copilot.tools` | ✅ |
| `copilot.canvas` | ✅ |

### 1.3 `__version__`

`copilot.__version__` 存在,值为字符串 `"1.0.1"`(通过 `importlib.metadata` 取的,卸载时回退为 `"0.0.0.dev0"`)。

---

## 2. CopilotClient 构造函数(原 §"SubprocessConfig 字段")

**SubprocessConfig 已整体移除**。1.0.1 拆分为两层:

### 2.1 `CopilotClient.__init__` 完整签名

```python
def __init__(
    self,
    *,
    connection: RuntimeConnection | None = None,    # 替代 SubprocessConfig
    working_directory: str | None = None,           # 从 SubprocessConfig 提到顶层
    log_level: LogLevel = "info",                   # 从 SubprocessConfig 提到顶层
    env: dict[str, str] | None = None,              # 从 SubprocessConfig 提到顶层
    github_token: str | None = None,                # 从 SubprocessConfig 提到顶层
    base_directory: str | None = None,              # 新增(等价于 COPILOT_HOME)
    use_logged_in_user: bool | None = None,         # 新增
    telemetry: TelemetryConfig | None = None,       # 新增
    session_fs: SessionFsConfig | None = None,      # 新增
    session_idle_timeout_seconds: int | None = None,# 新增
    enable_remote_sessions: bool = False,           # 新增
    on_list_models: Callable | None = None,         # 新增
    mode: CopilotClientMode = 'copilot-cli',        # 新增
)
```

**所有参数都是 keyword-only**(`*` 之后),不能位置传。0.2.2 的 `CopilotClient(client_config, auto_start=True)` 在 1.0.1 会 `TypeError`。

### 2.2 0.2.2 字段 → 1.0.1 映射

| 0.2.2 `SubprocessConfig` 字段 | 1.0.1 位置 | 备注 |
|-------|-------|------|
| `cli_path: str` | `StdioRuntimeConnection(path=...)` | 路径现在是 connection 的属性 |
| `cwd: str` | `CopilotClient(working_directory=...)` | 改名?原 0.2.2 也叫 cwd,1.0.1 改 working_directory |
| `github_token: str` | `CopilotClient(github_token=...)` | 提到顶层 |
| `log_level: str` | `CopilotClient(log_level=...)` | 提到顶层,值限定为 `Literal["none","error","warning","info","debug","all"]` |
| `env: dict` | `CopilotClient(env=...)` | 提到顶层 |
| (无) | `CopilotClient(base_directory=...)` | 新增,等价于设置 `COPILOT_HOME` |
| (无) | `CopilotClient(use_logged_in_user=...)` | 新增,默认 `None`(若没设 github_token 解析为 `True`) |

### 2.3 RuntimeConnection 子类

```python
@dataclass
class StdioRuntimeConnection(ChildProcessRuntimeConnection):
    path: str | None = None
    args: Sequence[str] = ()

@dataclass
class TcpRuntimeConnection(ChildProcessRuntimeConnection):
    path: str | None = None
    args: Sequence[str] = ()
    port: int = 0
    connection_token: str | None = None

@dataclass
class UriRuntimeConnection(RuntimeConnection):
    url: str = ""
    connection_token: str | None = None

# 静态工厂方法(在 RuntimeConnection 基类上)
RuntimeConnection.for_stdio(path=None, args=())       -> StdioRuntimeConnection
RuntimeConnection.for_tcp(port=0, connection_token=None, path=None, args=()) -> TcpRuntimeConnection
RuntimeConnection.for_uri(url, connection_token=None) -> UriRuntimeConnection
```

**`auto_start` 参数已移除** — 1.0.1 必须显式 `await client.start()`,没"构造即启动"选项。

---

## 3. `create_session` kwargs 变化

### 3.1 完整 kwargs(摘录主插件用到的)

```python
async def create_session(
    self,
    on_permission_request: _PermissionHandlerFn | None = None,
    model: str | None = None,
    session_id: str | None = None,
    client_name: str | None = None,
    reasoning_effort: ReasoningEffort | None = None,
    reasoning_summary: ReasoningSummary | None = None,
    context_tier: ContextTier | None = None,
    tools: list[Tool] | None = None,
    system_message: SystemMessageConfig | None = None,
    available_tools: list[str] | ToolSet | None = None,
    excluded_tools: list[str] | ToolSet | None = None,
    on_user_input_request: UserInputHandler | None = None,
    hooks: SessionHooks | None = None,
    working_directory: str | None = None,
    provider: ProviderConfig | None = None,
    streaming: bool | None = None,
    include_sub_agent_streaming_events: bool | None = None,
    mcp_servers: dict[str, MCPServerConfig] | None = None,
    custom_agents: list[CustomAgentConfig] | None = None,
    default_agent: DefaultAgentConfig | dict[str, Any] | None = None,
    agent: str | None = None,
    config_directory: str | None = None,                  # <-- 原 config_dir 改名
    skill_directories: list[str] | None = None,
    disabled_skills: list[str] | None = None,
    infinite_sessions: InfiniteSessionConfig | None = None,  # TypedDict,可传 dict
    large_output: LargeToolOutputConfig | None = None,
    on_event: Callable[[SessionEvent], None] | None = None,
    commands: list[CommandDefinition] | None = None,
    on_elicitation_request: ElicitationHandler | None = None,
    enable_mcp_apps: bool = False,
    github_token: str | None = None,
    # ... 很多新参数(本插件不直接用)
)
```

### 3.2 主插件 `_build_session_config` (L7787-7934) 字段映射

| 主插件 session_params | 1.0.1 状态 |
|----------------------|----------|
| `session_id` | ✅ 仍存在 |
| `model` | ✅ |
| `streaming` | ✅ |
| `tools` | ✅(但参数类型 `list[Tool] \| None` — `Tool` 现在是 public 类,`define_tool` 工厂未变) |
| `system_message` | ✅ 类型改为 `SystemMessageConfig`(可能内部也变了,PR 3 需查) |
| `config_dir` | ❌ **改名为 `config_directory`** |
| `infinite_sessions` | ✅ 仍存在,类型 `InfiniteSessionConfig` |
| `working_directory` | ✅ |
| `on_permission_request` | ✅ |
| `reasoning_effort` | ✅ |
| `mcp_servers` | ✅ 但类型现在是 `dict[str, MCPStdioServerConfig \| MCPHTTPServerConfig]` |
| `available_tools` | ✅ |
| `provider` | ✅(ProviderConfig 类仍在) |
| `hooks` | ✅(类型 `SessionHooks`) |
| `skill_directories` | ✅ |
| `disabled_skills` | ✅ |
| `custom_agents` | ✅ |
| `agent` | ✅ |

### 3.3 `resume_session` 差异

`resume_session` 比 `create_session` 多了两个独有参数:
- `continue_pending_work: bool | None = None`
- `open_canvases: list[OpenCanvasInstance] | None = None`

其余 kwargs 与 `create_session` 基本一致。

---

## 4. Session / CopilotSession 方法

**类名从 `Session` 改为 `CopilotSession`**。`from copilot import Session` 现在会失败;`from copilot.session import CopilotSession` 可用。

### 4.1 关键方法签名

```python
class CopilotSession:
    async def send(
        self,
        prompt: str,                                    # 位置参数,不是 dict
        *,
        attachments: list[Attachment] | None = None,
        mode: Literal['enqueue', 'immediate'] | None = None,
        agent_mode: Literal['interactive', 'plan', 'autopilot', 'shell'] | None = None,
        request_headers: dict[str, str] | None = None,
        display_prompt: str | None = None,
    ) -> str:                                            # 返回 session_id 字符串

    async def send_and_wait(
        self,
        prompt: str,
        *,
        attachments: list[Attachment] | None = None,
        mode: Literal['enqueue', 'immediate'] | None = None,
        agent_mode: Literal['interactive', 'plan', 'autopilot', 'shell'] | None = None,
        request_headers: dict[str, str] | None = None,
        display_prompt: str | None = None,
        timeout: float = 60.0,
    ) -> SessionEvent | None:

    async def abort(self) -> None:
    async def disconnect(self) -> None:                  # <-- 替代 destroy
    # destroy 已移除
    # get_messages 已移除

    def on(self, handler: Callable[[SessionEvent], None]) -> Callable[[], None]:
    # workspace_path 是 functools.cached_property(实例属性)
    # session_id 是实例属性(create_session 返回时已存在)
```

### 4.2 0.2.2 写法 → 1.0.1 写法

| 0.2.2 写法 | 1.0.1 状态 | PR 3 改动 |
|-------|-------|----------|
| `session.send({"prompt": "..."})` | ❌ 不能传 dict,必须 `session.send("...")` | 改 1 处 |
| `session.send_and_wait({"prompt": "..."})` | ❌ 同上 | 改 1 处 |
| `session.send("...", mode="immediate")` | ✅ 仍合法 | 不变 |
| `await session.destroy()` | ❌ 已移除,改 `disconnect` | L9614 |
| `session.get_messages()` | ❌ 已移除(没替代方法,本插件未用) | 不变 |
| `session.workspace_path` | ✅ `functools.cached_property`(懒加载) | 不变 |

---

## 5. RPC 类型重命名

### 5.1 Mode 相关

| 0.2.2 | 1.0.1 | 备注 |
|-------|-------|------|
| `from copilot.generated.rpc import Mode` | `from copilot.generated.rpc import SessionMode` | 名字改了 |
| `Mode.INTERACTIVE` / `Mode.PLAN` / `Mode.AUTOPILOT` | `SessionMode.INTERACTIVE` / `.PLAN` / `.AUTOPILOT` | 枚举成员名未变,值 `'interactive' / 'plan' / 'autopilot'` |
| `from copilot.generated.rpc import SessionModeSetParams` | `from copilot.generated.rpc import ModeSetRequest` | 名字改了 |
| `SessionModeSetParams(mode=...)` | `ModeSetRequest(mode=...)` | 用法基本一致 |
| `session.rpc.mode.set(SessionModeSetParams(mode=...))` | `session.rpc.mode.set(ModeSetRequest(mode=...))` | L9421, L9505 |

### 5.2 `ModeApi` 签名

```python
class ModeApi:
    async def get(self, *, timeout: float | None = None) -> SessionMode
    async def set(self, params: ModeSetRequest, *, timeout: float | None = None) -> None
```

### 5.3 其他 RPC 类型

| 0.2.2 名字 | 1.0.1 名字 | 备注 |
|-------|-------|------|
| `SessionModeSetParams` | `ModeSetRequest` | 上面已述 |
| `Mode` | `SessionMode` | 上面已述 |
| (没有的) | `SendMode`、`SendAgentMode`、`SessionOpenOptionsEnvValueMode` 等 | 新增,本插件未用 |
| `ModelCapabilities` | `ModelCapabilities` | 仍在,但字段大幅扩充 |
| `SessionEvent` | `SessionEvent` | 仍在,但 data 字段改了(见 §7) |

---

## 6. InfiniteSessionConfig

| 主题 | 1.0.1 实际 |
|------|----------|
| 形态 | `TypedDict, total=False` |
| 字段 | `enabled: bool`、`background_compaction_threshold: float`、`buffer_exhaustion_threshold: float` |
| 用法 | `create_session(infinite_sessions={"enabled": True, "background_compaction_threshold": 0.8, "buffer_exhaustion_threshold": 0.9})` |
| 状态 | ✅ **与原计划假设完全一致** |

主插件 L7810-7818 的 `InfiniteSessionConfig(enabled=..., ...)` 应改为 `{"enabled": ..., ...}` 字典字面量。

---

## 7. 事件 payload 字段(最高风险)

下面只列主插件 `_event_handler` 通过 `safe_get_data_attr(event, "...")` 实际读到的字段,标注 1.0.1 实际字段名。

### 7.1 字段兼容性表

| 事件类型 | 主插件当前读 | 1.0.1 实际字段 | 兼容性 |
|---------|------------|------------|------|
| `assistant.message_delta` | `delta_content` | `delta_content`、`message_id`、`parent_tool_call_id` | ✅ 直接兼容 |
| `assistant.message` | `content` | `content`、`message_id`、`model`、`phase`、`tool_requests`、… | ✅ 兼容(主插件只读 `content`) |
| `assistant.intent` | `intent` | `intent` | ✅ |
| `assistant.reasoning_delta` | `delta_content` | `delta_content`、`reasoning_id` | ✅ |
| `tool.execution_start` | `tool_call_id`、`name`、`arguments` | `tool_call_id`、`tool_name`、`arguments`、… | ⚠️ **`name` 改 `tool_name`** |
| `tool.execution_complete` | `tool_call_id`、`name`、`result` | `tool_call_id`、`result`、`success`、… | ⚠️ **`name` 已不存在**,只有 `tool_name` |
| `tool.execution_progress` | `progress`、`message` | `progress_message`、`tool_call_id` | ⚠️ **`progress` 改 `progress_message`** |
| `tool.execution_partial_result` | `partial_result` | `partial_output`、`tool_call_id` | ⚠️ **`partial_result` 改 `partial_output`** |
| `subagent.started` | `name`、`tool_call_id` | `agent_name`、`agent_display_name`、`tool_call_id`、… | ⚠️ **`name` 改 `agent_name`** |
| `subagent.completed` | `name`、`tool_call_id` | `agent_name`、`tool_call_id`、`total_tokens`、… | ⚠️ **`name` 改 `agent_name`** |
| `subagent.failed` | `name`、`error`、`tool_call_id` | `agent_name`、`error`、`tool_call_id`、… | ⚠️ **`name` 改 `agent_name`** |
| `session.compaction_start` | (无字段) | `conversation_tokens`、`system_tokens`、`tool_definitions_tokens` | ✅(主插件不读) |
| `session.compaction_complete` | (无字段) | `success`、`checkpoint_path`、`messages_removed`、… | ✅(主插件不读) |
| `session.plan_changed` | `operation` | `operation` | ✅ |
| `session.context_changed` | `new_context` | `cwd`、`branch`、`base_commit`、`head_commit`、`git_root`、`repository`、`repository_host`、`host_type` | ❌ **`new_context` 已不存在**,整组重命名 |
| `assistant.usage` | `input_tokens`、`output_tokens` | `input_tokens`、`output_tokens`、`cache_read_tokens`、`reasoning_tokens`、… | ✅(主插件只读前两个) |
| `session.error` | `message` | `message`、`error_type`、`error_code`、`stack`、… | ✅(主插件只读 `message`) |
| `skill.invoked` | `name` | `name`、`path`、`plugin_name`、… | ✅ |
| `session.idle` | (无字段) | `aborted` | ✅(主插件不读) |
| `permission.requested` | (主插件用回调,不直接读 data) | `permission_request`、`request_id`、`prompt_request`、`resolved_by_hook` | ✅(主插件通过 `on_permission_request` 回调处理) |

### 7.2 新增事件(主插件无需处理,但需知会)

- `subagent.selected` / `subagent.deselected` — subagent 选择/取消事件
- `session.lifecycle` 事件族 — 替代 0.2.2 的 `session.created/deleted/updated`,通过 `SessionLifecycleEvent` 统一
- `assistant.usage` 新增 `cache_read_tokens` / `cache_write_tokens` / `reasoning_tokens` 等 token 字段

### 7.3 PR 3 修复策略

主插件的 `safe_get_data_attr` (推测在 `_event_handler` 内部)应实现**新名优先 + 旧名 fallback**:

```python
def safe_get_data_attr(event, new_name, *legacy_names):
    """按优先级取属性: 新名 > 旧名 1 > 旧名 2"""
    if hasattr(event, "data") and event.data is not None:
        data = event.data
        for name in (new_name, *legacy_names):
            if hasattr(data, name):
                return getattr(data, name)
            # dataclass 还可能用 __dict__
            if isinstance(data, dict) and name in data:
                return data[name]
    return None
```

需要主插件 PR 3 改的具体事件处理:
- `tool.execution_start/complete`:`name` → `tool_name`
- `tool.execution_progress`:`progress` → `progress_message`(插件若读 `message` 也保留)
- `tool.execution_partial_result`:`partial_result` → `partial_output`
- `subagent.{started,completed,failed}`:`name` → `agent_name`
- `session.context_changed`:`new_context` 整段重写(读 `cwd` / `branch` / `repository` 等)
- 0.2.2 旧值如有 `message` 字段(在 `progress`/`partial_result` 之类的),`safe_get_data_attr` 也读新名 `progress_message`/`partial_output` 即可

---

## 8. MCP 服务器 type 字符串

### 8.1 类型

```python
class MCPStdioServerConfig(TypedDict, total=False):
    type: NotRequired[Literal['local', 'stdio']]   # 两个都支持
    tools: list[str]
    command: str
    args: NotRequired[list[str]]
    env: NotRequired[dict[str, str]]
    timeout: NotRequired[int]
    working_directory: NotRequired[str]

class MCPHTTPServerConfig(TypedDict, total=False):
    type: NotRequired[Literal['http', 'sse']]      # 两个都支持
    tools: list[str]
    url: str
    headers: NotRequired[dict[str, str]]
    timeout: NotRequired[int]
```

### 8.2 主插件 `_parse_mcp_servers` (L5640+) 兼容策略

原插件(0.2.2)逻辑可能是:
- 收到 `mcp_server = {"name": ..., "url": ...}` → 输出 `{name: {"type": "remote", "url": ...}}`
- 收到 `mcp_server = {"name": ..., "command": ...}` → 输出 `{name: {"type": "local", "command": ...}}`

1.0.1 `MCPServerConfig` 是 `MCPStdioServerConfig | MCPHTTPServerConfig` 的 Union,字段 `type` 可省略,SDK 内部根据是否有 `url` 自动判断。

**PR 3 改动建议**:把 `type` 字段从输出 dict 里删掉(SDK 会自动判别);若必须显式,按以下规则:
- 走 stdio/命令 → `type: "local"` 或 `"stdio"`(两个都接受)
- 走 url → `type: "http"` 或 `"sse"`(两个都接受,SDK 内部根据协议头判别)

### 8.3 字段重命名

`_mcp_servers_to_wire` 内部把 `working_directory` 转 `cwd`(**对调用方透明**,主插件输出的 key 仍是 `working_directory`)。

---

## 9. 权限 outcome 字符串(仅参考,本插件未自定义)

| 0.2.2 | 1.0.1 |
|-------|-------|
| `"approved"` | `"approve-once"` |
| `"denied-interactively-by-user"` | `"reject"` |
| `"denied-no-approval-rule-and-could-not-request-from-user"` | `"user-not-available"` |
| (不存在) | `"approve-for-session"` (新) |
| (不存在) | `"approve-for-location"` (新) |

`PermissionHandler.approve_all` 签名未变(`request, invocation -> PermissionRequestResult`),本插件不受影响。

---

## 10. 烟雾测试结果(`/tmp/sdk_gate.py`)

### 10.1 输出(2026-06-13, 无 GH_TOKEN, 跑 [1]-[4])

```
[1] Imports: OK (Mode→SessionMode enum, StdioRuntimeConnection 替代 SubprocessConfig)
[2] Client started: OK type=CopilotClient
[3] list_models: OK 3 models, first.id=auto
[4] create_session: OK session_id=b5112d1b-7d0c-4223-b9a9-84c3e5c8ee99, type=CopilotSession
[5] session.send: SKIPPED — no GH_TOKEN env
[6] cleanup: SKIPPED
```

### 10.2 关键验证

- ✅ `from copilot import CopilotClient, define_tool` — 顶层导出
- ✅ `from copilot.session import PermissionHandler, CopilotSession` — 公开类可导入
- ✅ `from copilot.generated.rpc import ModeSetRequest, SessionMode` — RPC 类型可导入
- ✅ `from copilot.client import StdioRuntimeConnection` — 新连接类型可导入
- ✅ `CopilotClient(connection=StdioRuntimeConnection(), log_level="info")` — 构造 + start 成功
- ✅ `await client.list_models()` — 返回 3 个 model,`ModelInfo.id` 字段存在
- ✅ `await client.create_session(model=..., on_permission_request=PermissionHandler.approve_all, infinite_sessions={"enabled": False})` — 成功,返回 `CopilotSession`,`session_id` 已是 UUID
- ❌ [5] `session.send` — 未跑(无 GH_TOKEN)
- ❌ [6] `session.disconnect` + `client.stop` — 未跑(无 GH_TOKEN)

### 10.3 完整链测试条件

需要 `GH_TOKEN` 环境变量,有 GitHub Copilot 订阅。完整测试脚本保留在 `/tmp/sdk_gate.py`,PR 3 完成后再跑一次 [1]-[6] 全套。

---

## 11. 关键发现与后续 PR 决策

### 11.1 PR 2 (companion 脚本)需改的额外点

原 plan §2.3 的 8 个文件改动中,以下几处需要调整:

| 文件 | 原 plan 假设 | 1.0.1 实际 | 调整 |
|------|------------|-----------|------|
| `tests/verify_persistence.py` L25 | `CopilotClient({"config_dir": ...})` | `CopilotClient` 全部 keyword-only,且**没有 `config_dir` 这个 client kwarg** | 改为 `CopilotClient(connection=StdioRuntimeConnection(), working_directory=..., log_level=...)`,session 的 `config_dir` 改 `config_directory` |
| `tests/discover_default_prompt.py` L15 | `CopilotClient()` | `CopilotClient(connection=StdioRuntimeConnection())`(加显式 connection) | 同上 |
| `tests/discover_byok_prompt.py` | 同上 | 同上 | 同上 |
| `scripts/test_sdk.py` L64 | `create_session(config=session_config)` | `create_session(**session_config)` | 不变 |
| `scripts/sync_to_workspace.py` | 错误信息 + 需要 `SubprocessConfig()` | 需 `StdioRuntimeConnection()` 替代 | 改 |
| `debug/test_system_message_resume.py` L24 | 删除 `from copilot.types import SessionConfig` | `copilot.types` 已删除,改为 `from copilot.session import CopilotSession` 等 | 改 |
| `test_sort.py` L59 | `from copilot.client import SubprocessConfig` | `from copilot.client import StdioRuntimeConnection` | 改 |
| `workspace_skills_example.py` L229 | 删除 `# from copilot.types import Tool` 注释 | `from copilot import Tool` 仍是公开导出(类型已变) | 注释可删,但若要类型注解要 `from copilot import Tool` |

### 11.2 PR 3 (主插件)需改的实际行数

**比原 plan 8 处多得多**,至少 20+ 处:

| 区域 | 改动 | 行数估计 |
|------|------|---------|
| L8-L9 | `version` 0.13.2 → 0.14.0,`requirements` 0.2.2 → 1.0.1 | 2 |
| L36 | `import aiohttp` 之类需保留(只是 aiohttp 是 plugin 业务依赖,跟 SDK 无关) | 0 |
| L38 | `from copilot.generated.rpc import Mode, SessionModeSetParams` → `from copilot.generated.rpc import SessionMode, ModeSetRequest` | 1 |
| L42-46 | `PermissionHandler` 稳定,1.0.1 直接可用,但仍建议保留 try/except 兜底以防 runtime import 异常 | 0-1 |
| L7300-7375 (`_build_client_config`) | **整段重写**:`from copilot.client import StdioRuntimeConnection`,改成 `client_config = StdioRuntimeConnection(path=cli_path)`,然后 `CopilotClient(connection=client_config, working_directory=cwd, log_level=..., env=..., github_token=token)`(而不是 `SubprocessConfig(**client_config)`) | **~15 行** |
| L7787-7934 (`_build_session_config`) | 字段名 `config_dir` → `config_directory`;session_params 字典原样透传 | 1-2 行 |
| L7810-7818 (InfiniteSessionConfig) | `InfiniteSessionConfig(enabled=..., ...)` → `{"enabled": ..., ...}` | 1 行 |
| L8462 | `CopilotClient(client_config, auto_start=True)` → `client = CopilotClient(connection=client_config)`;然后 `await client.start()` 显式调用;`auto_start` kwarg 已移除 | 2-3 行 |
| L9196、L9399、L9483 | `CopilotClient(client_config)` → `CopilotClient(connection=client_config)`(位置→keyword)| 3 |
| L9421、L9505 | `SessionModeSetParams(mode=mode_enum)` → `ModeSetRequest(mode=mode_enum)`,且 `mode_enum` 是 `SessionMode.X` | 2 |
| L9599-9603、L10570-10574 | `send(prompt, mode="immediate")` 仍合法(位置参数)| 0 |
| L9614 | `await session.destroy()` → `await session.disconnect()`(彻底移除 try/except,因为 `destroy` 已不存在)| 1 |
| `_event_handler` 各 `safe_get_data_attr` | 至少 6 处字段名修复(`name`→`tool_name`/`agent_name`、`progress`→`progress_message`、`partial_result`→`partial_output`、整组 `new_context` 重写) | 6-10 处 |
| `script_path` 路径 | `scripts/test_sdk.py` 等 8 个文件(由 PR 2 处理) | — |

### 11.3 PR 4 (部署)需改

- `scripts/deploy_pipe.py` L82:`"requirements": "github-copilot-sdk==0.1.25"` → `==1.0.1`(原 plan 已列)

### 11.4 🚫 新增风险(原 plan 未列)

| 风险 | 说明 |
|------|------|
| `auto_start` 移除 | 主插件 0.2.2 写法 `CopilotClient(client_config, auto_start=True)` 依赖自动启动,1.0.1 必须显式 `await client.start()`。**如果主插件在 L8462 用 try/except 包装了构造,那 L8462 现在每次都成功但 client 不会连上 CLI 进程,后续 `list_models`/`create_session` 会卡住或报连接错误**。 |
| `CopilotClient` 全部 keyword-only | 主插件在 L9196、L9399、L9483 用 `CopilotClient(client_config)` 位置传,1.0.1 会 `TypeError: takes 1 positional argument`。 |
| `session.send` 必须位置参数 | 0.2.2 可以 `session.send({"prompt": "..."})`,1.0.1 必须是 `session.send("...")`。如果主插件有 `send({"prompt": ...})` 写法,需全数修正。 |
| `InfiniteSessionConfig` 不能再 dataclass 化 | L7814-7818 写的是 `InfiniteSessionConfig(enabled=..., ...)` 构造函数调用,1.0.1 它是 TypedDict,不能 `()` 调用,只能 dict 字面量。 |
| `session.workspace_path` 是 `cached_property` | 0.2.2 可能是普通属性,1.0.1 是 `functools.cached_property`(懒计算)。**若访问时 workspace_path 还没建立(极端 race),首次访问会抛 AttributeError**。建议在 `await session.send(...)` 之后再读 `session.workspace_path`。 |

---

## 12. 一页纸决策清单(给 PR 3 用)

- [ ] `_build_client_config`:返回 `StdioRuntimeConnection(path=cli_path, args=[])`,然后 `CopilotClient(connection=conn, working_directory=cwd, log_level=..., env=..., github_token=token, base_directory=...)`(**全部 keyword-only**)
- [ ] `_build_session_config`:`config_dir` → `config_directory`
- [ ] `InfiniteSessionConfig(...)` → `{...}` 字典
- [ ] `from copilot.generated.rpc import SessionMode, ModeSetRequest`(改 import)
- [ ] `session.rpc.mode.set(ModeSetRequest(mode=SessionMode.X))`(改参数类型)
- [ ] `CopilotClient(client_config, auto_start=True)` → `CopilotClient(connection=client_config)` + 显式 `await client.start()`
- [ ] `await session.destroy()` → `await session.disconnect()`(去掉 try/except)
- [ ] `safe_get_data_attr(event, "tool_name", "name")` for `tool.execution_start/complete`
- [ ] `safe_get_data_attr(event, "agent_name", "name")` for `subagent.*`
- [ ] `safe_get_data_attr(event, "progress_message", "progress", "message")` for `tool.execution_progress`
- [ ] `safe_get_data_attr(event, "partial_output", "partial_result")` for `tool.execution_partial_result`
- [ ] `session.context_changed` 处理整段重写,读 `cwd`/`branch`/`repository`/`host_type`/`git_root`(没有 `new_context`)
- [ ] 6 个 `CopilotClient(client_config)` 位置调用 → 全部加 `connection=` keyword
- [ ] `version: 0.13.2` → `0.14.0`,`requirements: github-copilot-sdk==0.2.2` → `==1.0.1`
- [ ] 删除 `_parse_mcp_servers` 输出 dict 中的 `type` 字段(SDK 会自动判别);如必须,用 `"local"`/`"stdio"`/`"http"`/`"sse"`
