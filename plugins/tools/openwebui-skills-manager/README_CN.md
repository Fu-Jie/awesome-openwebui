# 🧰 OpenWebUI Skills 管理工具

| 作者：[Fu-Jie](https://github.com/Fu-Jie) · v0.3.3 | [⭐ 点个 Star 支持项目](https://github.com/Fu-Jie/openwebui-extensions) |
| :--- | ---: |

| ![followers](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_followers.json&label=%F0%9F%91%A5&style=flat) | ![points](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_points.json&label=%E2%AD%90&style=flat) | ![top](https://img.shields.io/badge/%F0%9F%8F%86-Top%20%3C1%25-10b981?style=flat) | ![contributions](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_contributions.json&label=%F0%9F%93%A6&style=flat) | ![downloads](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_downloads.json&label=%E2%AC%87%EF%B8%8F&style=flat) | ![saves](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_saves.json&label=%F0%9F%92%BE&style=flat) | ![views](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_views.json&label=%F0%9F%91%81%EF%B8%8F&style=flat) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |

一个 OpenWebUI 原生 Tool 插件，用于让任意模型直接管理 **Workspace > Skills**。

## 使用 Batch Install Plugins 安装

如果你已经安装了 [Batch Install Plugins from GitHub](https://openwebui.com/posts/batch_install_plugins_install_popular_plugins_in_s_c9fd6e80)，可以用下面这句来安装或更新当前插件：

```text
从 Fu-Jie/openwebui-extensions 安装插件
```

当选择弹窗打开后，搜索当前插件，勾选后继续安装即可。

> [!IMPORTANT]
> 如果你已经安装了 OpenWebUI 官方社区里的同名版本，请先删除旧版本，否则重新安装时可能报错。删除后，Batch Install Plugins 后续就可以继续负责更新这个插件。

## 最新更新

- **🛡️ 破坏性操作确认**：新增 `REQUIRE_CONFIRMATION` 阀门（默认 `True`），在执行 `update_skill`、`delete_skill` 以及 `create_skill`/`install_skill` 触发覆盖前通过 `__event_call__` 弹出用户确认。取消时返回结构化的 `{cancelled: true, ...}` 结果，并发出本地化的状态消息。
- **🌐 本地化确认文案**：所有新增的确认标题、提示信息和取消状态文案均已翻译至支持的 12 种语言。

> [!TIP]
> **💡 想要批量安装/管理全局插件 (Actions, Filters, Pipes, Tools)？**
> 本插件专注管理工作区的 AI 技能 (Skills)。如果你需要安装和管理全局函数型插件，请使用同系列的 [Batch Install Plugins from GitHub](https://openwebui.com/posts/batch_install_plugins_install_popular_plugins_in_s_c9fd6e80) 工具，不仅安装体验极致，而且完美接轨系统扩展体系。

## 核心特性

- **🌐 全模型可用**：只要模型启用了 OpenWebUI Tools，即可调用。
- **🛠️ 简化技能管理**：直接管理 OpenWebUI Skills 记录。
- **🔐 用户范围安全**：仅操作当前用户可访问的技能。
- **📡 友好状态反馈**：每一步操作都有状态栏提示。
- **🔍 自动发现**：自动发现并安装 GitHub 仓库目录树中的所有 skill。
- **⚙️ 智能去重**：批量安装时自动清除重复 URL，检测冲突的 skill 名称。

## 使用方法

1. 打开 OpenWebUI，进入 **Workspace > Tools**。
2. 在官方市场安装 **OpenWebUI Skills 管理工具**。
3. 为当前模型/聊天启用该工具。
4. 在对话中让模型调用，例如：
   - “列出我的 skills”
   - “显示名为 docs-writer 的 skill”
   - “创建一个 meeting-notes 技能，内容是 ...”
   - “更新某个 skill ...”
   - “删除某个 skill ...”

### 手动安装（备选）

- 新建 Tool，粘贴 `openwebui_skills_manager.py`。

## 示例：安装技能 (Install Skills)

该工具支持从 URL 直接抓取并安装技能（支持 GitHub 仓库根、tree/blob 链接、原始 Markdown 链接以及 .zip/.tar 压缩包）。

### 自动发现 GitHub 仓库中的所有 skill

- "从 <https://github.com/nicobailon/visual-explainer> 安装 skill" ← 自动发现所有子目录
- "从 <https://github.com/anthropics/skills> 安装所有 skill" ← 安装整个技能目录

### 从 GitHub 安装单个技能

- “从 <https://github.com/anthropics/skills/tree/main/skills/xlsx> 安装技能”
- “安装技能 <https://github.com/Fu-Jie/openwebui-extensions/blob/main/.agent/skills/test-copilot-pipe/SKILL.md”>

### 批量安装多个技能

- “安装这些技能：['https://github.com/anthropics/skills/tree/main/skills/xlsx', 'https://github.com/anthropics/skills/tree/main/skills/docx']”

> **提示**：对于 GitHub 链接，工具会自动处理目录（tree）地址，并尝试查找目录下的 `SKILL.md`。
>
## 安装逻辑

### URL 类型识别与处理

`install_skill` 方法自动检测和处理不同的 URL 格式，具体逻辑如下：

#### **1. GitHub 仓库根目录**（自动发现）

**格式：** `https://github.com/owner/repo` 或 `https://github.com/owner/repo/`

**处理流程：**

1. 通过正则表达式检测：`^https://github\.com/([^/]+)/([^/]+)/?$`
2. 自动转换为：`https://github.com/owner/repo/tree/main`
3. API 查询所有子目录：`/repos/{owner}/{repo}/contents?ref=main`
4. 为每个子目录创建技能 URL
5. 尝试从每个目录中获取 `SKILL.md`
6. 所有发现的技能以**批量模式**安装

**示例流程：**

```
输入：https://github.com/nicobailon/visual-explainer
      ↓ [检测：仓库根]
      ↓ [转换：添加 /tree/main]
      ↓ [查询：GitHub API 子目录]
发现：skill1, skill2, skill3, ...
      ↓ [批量模式]
安装：所有发现的技能
```

#### **2. GitHub Tree（目录）URL**（自动发现）

**格式：** `https://github.com/owner/repo/tree/branch/path/to/directory`

**处理流程：**

1. 通过检测 `/tree/` 路径识别
2. API 查询目录内容：`/repos/{owner}/{repo}/contents/path?ref=branch`
3. 筛选子目录（跳过 `.hidden` 隐藏目录）
4. 为每个子目录尝试获取 `SKILL.md`
5. 所有发现的技能以**批量模式**安装

**示例：**

```
输入：https://github.com/anthropics/skills/tree/main/skills
      ↓ [查询：/repos/anthropics/skills/contents/skills?ref=main]
发现：xlsx, docx, pptx, markdown, ...
安装：批量安装所有 12 个技能
```

#### **3. GitHub Blob（文件）URL**（单个安装）

**格式：** `https://github.com/owner/repo/blob/branch/path/to/SKILL.md`

**处理流程：**

1. 通过 `/blob/` 模式检测
2. 转换为原始 URL：`https://raw.githubusercontent.com/owner/repo/branch/path/to/SKILL.md`
3. 获取内容并作为单个技能解析
4. 以**单个模式**安装

**示例：**

```
输入：https://github.com/user/repo/blob/main/SKILL.md
      ↓ [转换：/blob/ → raw.githubusercontent.com]
      ↓ [获取：原始 markdown 内容]
解析：技能名称、描述、内容
安装：单个技能
```

#### **4. GitHub Raw URL**（单个安装）

**格式：** `https://raw.githubusercontent.com/owner/repo/branch/path/to/SKILL.md`

**处理流程：**

1. 从原始内容端点直接下载
2. 作为 Markdown 格式解析（包括 frontmatter）
3. 提取技能元数据（名称、描述等）
4. 以**单个模式**安装

**示例：**

```
输入：https://raw.githubusercontent.com/Fu-Jie/openwebui-extensions/main/SKILL.md
      ↓ [直接获取原始内容]
解析：提取元数据
安装：单个技能
```

#### **5. 压缩包文件**（单个安装）

**格式：** `https://example.com/skill.zip` 或 `.tar`, `.tar.gz`, `.tgz`

**处理流程：**

1. 通过文件扩展名检测：`.zip`, `.tar`, `.tar.gz`, `.tgz`
2. 下载并安全解压：
   - 验证成员路径（防止目录遍历攻击）
   - 解压到临时目录
3. 在压缩包根目录查找 `SKILL.md`
4. 解析内容并以**单个模式**安装

**示例：**

```
输入：https://github.com/user/repo/releases/download/v1.0/my-skill.zip
      ↓ [下载：zip 压缩包]
      ↓ [安全解压：验证路径]
      ↓ [查找：SKILL.md]
解析：提取元数据
安装：单个技能
```

### 批量模式 vs. 单个模式

| 模式 | 触发条件 | 行为 | 结果 |
|------|---------|------|------|
| **批量** | 仓库根或 tree URL | 自动发现所有子目录 | { succeeded, failed, results } |
| **单个** | Blob、Raw 或压缩包 URL | 直接获取并解析内容 | { success, id, name, ... } |
| **批量** | URL 列表 | 逐个处理每个 URL | 结果列表 |

### 批量安装时的去重

提供多个 URL 进行批量安装时：

1. **URL 去重**：移除重复 URL（保持顺序）
2. **名称冲突检测**：跟踪已安装的技能名称
   - 相同名称出现多次 → 发送警告通知
   - 行为取决于 `ALLOW_OVERWRITE_ON_CREATE` 参数

**示例：**

```
输入 URL：[url1, url1, url2, url2, url3]
         ↓ [去重]
唯一：    [url1, url2, url3]
处理：    3 个 URL
输出：    「已从批量队列中移除 2 个重复 URL」
```

### 技能名称识别

解析时，技能名称按以下优先级解析：

1. **用户指定的名称**（通过 `name` 参数）
2. **Frontmatter 元数据**（文件开头的 `---` 块）
3. **Markdown h1 标题**（第一个 `# 标题` 文本）
4. **提取的目录/文件名**（从 URL 路径）
5. **备用名称：** `"installed-skill"`（最后的选择）

**示例：**

```
Markdown 文档结构：
───────────────────────────
---
title: "我的自定义技能"
description: "做一些有用的事"
---

# 替代标题

内容...
───────────────────────────

识别优先级：
1. 检查 frontmatter：title = "我的自定义技能" ✓ 使用此项
2. （跳过其他选项）

结果：创建技能名为 "我的自定义技能"
```

### 安全与防护

所有安装都强制执行：

- ✅ **域名白名单**（TRUSTED_DOMAINS）：仅允许 github.com、huggingface.co、githubusercontent.com
- ✅ **方案验证**：仅接受 http/https URL
- ✅ **路径遍历防护**：压缩包解压前验证
- ✅ **用户隔离**：每个用户的操作隔离
- ✅ **超时保护**：可配置超时（默认 12 秒）

### 错误处理

| 错误情况 | 处理方式 |
|---------|---------|
| 不支持的方案（ftp://、file://） | 在验证阶段阻止 |
| 不可信的域名 | 拒绝（域名不在白名单中） |
| URL 获取超时 | 超时错误并建议重试 |
| 无效压缩包 | 解压时报错 |
| 未找到 SKILL.md | 每个子目录报错（批量继续） |
| 重复技能名 | 警告通知（取决于参数） |
| 缺少技能名称 | 错误（名称是必需的） |

## 配置参数（Valves）

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `SHOW_STATUS` | `True` | 是否在 OpenWebUI 状态栏显示操作状态。 |
| `REQUIRE_CONFIRMATION` | `True` | 在执行破坏性操作（`update_skill`、`delete_skill`，以及 `create_skill`/`install_skill` 触发覆盖）前要求用户进行一次是/否确认。关闭后，这些操作将不再弹出提示直接执行。 |
| `ALLOW_OVERWRITE_ON_CREATE` | `False` | 是否允许 `create_skill`/`install_skill` 默认覆盖同名技能。 |
| `INSTALL_FETCH_TIMEOUT` | `12.0` | 从 URL 安装技能时的请求超时时间（秒）。 |
| `TRUSTED_DOMAINS` | `github.com,huggingface.co,githubusercontent.com` | 逗号分隔的主信任域名清单（**必须启用**）。子域名会自动放行（如 `github.com` 允许 `api.github.com`）。详见 [域名白名单指南](https://github.com/Fu-Jie/openwebui-extensions/blob/main/plugins/tools/openwebui-skills-manager/docs/DOMAIN_WHITELIST.md)。 |

## 支持的方法

| 方法 | 用途 |
| --- | --- |
| `list_skills` | 列出当前用户的技能。 |
| `show_skill` | 通过 `skill_id` 或 `name` 查看单个技能。 |
| `install_skill` | 通过 URL 安装技能到 OpenWebUI 原生 Skills。 |
| `create_skill` | 创建新技能（或在允许时覆盖同名技能）。 |
| `update_skill` | 修改现有技能（通过 id 或 name）。支持更新：`new_name`（重命名）、`description`、`content` 或 `is_active`（启用/禁用）的任意组合。自动验证名称唯一性。 |
| `delete_skill` | 通过 `skill_id` 或 `name` 删除技能。 |

## 支持

如果这个插件对你有帮助，欢迎到 [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions) 点个 Star，这将是我持续改进的动力，感谢支持。

## 其他说明

- 本工具管理 OpenWebUI 原生 Skills 记录，并支持通过 URL 直接安装。
- 如需更复杂的工作流编排，可结合其他 Pipe/Tool 方案使用。

## 更新记录

完整历史请查看 GitHub 仓库的 commits 与 releases。
