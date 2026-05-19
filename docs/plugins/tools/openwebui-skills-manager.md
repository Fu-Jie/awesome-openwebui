# 🧰 OpenWebUI Skills Manager Tool

| By [Fu-Jie](https://github.com/Fu-Jie) · v0.3.3 | [⭐ Star this repo](https://github.com/Fu-Jie/openwebui-extensions) |
| :--- | ---: |

| ![followers](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_followers.json&label=%F0%9F%91%A5&style=flat) | ![points](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_points.json&label=%E2%AD%90&style=flat) | ![top](https://img.shields.io/badge/%F0%9F%8F%86-Top%20%3C1%25-10b981?style=flat) | ![contributions](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_contributions.json&label=%F0%9F%93%A6&style=flat) | ![downloads](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_downloads.json&label=%E2%AC%87%EF%B8%8F&style=flat) | ![saves](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_saves.json&label=%F0%9F%92%BE&style=flat) | ![views](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_views.json&label=%F0%9F%91%81%EF%B8%8F&style=flat) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |

A standalone OpenWebUI Tool plugin to manage native **Workspace > Skills** for any model.

## Install with Batch Install Plugins

If you already use [Batch Install Plugins from GitHub](https://openwebui.com/posts/batch_install_plugins_install_popular_plugins_in_s_c9fd6e80), you can install or update this plugin with:

```text
Install plugin from Fu-Jie/openwebui-extensions
```

When the selection dialog opens, search for this plugin, check it, and continue.

> [!IMPORTANT]
> If the official OpenWebUI Community version is already installed, remove it first. After that, Batch Install Plugins can keep this plugin updated in future runs.

## What's New

- **🛡️ Confirmation Before Destructive Actions**: New `REQUIRE_CONFIRMATION` valve (default `True`) prompts the user via `__event_call__` before `update_skill`, `delete_skill`, and overwrite paths in `create_skill`/`install_skill`. Cancellations return a structured `{cancelled: true, ...}` result with localized status messages.
- **🌐 Localized Confirmation Strings**: All new confirmation titles, messages, and cancellation statuses are translated across the 12 supported locales.

> [!TIP]
> **💡 Looking to batch install global plugins (Actions, Filters, Pipes, Tools)?**
> This plugin specializes in managing Workspace Skills for your assistants. If you need to install and manage global function-based plugins, use our companion tool [Batch Install Plugins from GitHub](https://openwebui.com/posts/batch_install_plugins_install_popular_plugins_in_s_c9fd6e80) for an optimized installation workflow.

## Key Features

- **🌐 Model-agnostic**: Can be enabled for any model that supports OpenWebUI Tools.
- **🛠️ Simple Skill Management**: Directly manage OpenWebUI skill records.
- **🔐 User-scoped Safety**: Operates on current user's accessible skills.
- **📡 Friendly Status Feedback**: Emits status bubbles for each operation.
- **🔍 Auto-Discovery**: Automatically discovers and installs all skills from GitHub repository trees.
- **⚙️ Smart Deduplication**: Removes duplicate URLs and detects conflicting skill names during batch installation.

## How to Use

1. Open OpenWebUI and go to **Workspace > Tools**.
2. Install **OpenWebUI Skills Manager Tool** from the official marketplace.
3. Enable this tool for your model/chat.
4. Ask the model to call tool operations, for example:
   - "List my skills"
   - "Show skill named docs-writer"
   - "Create a skill named meeting-notes with content ..."
   - "Update skill ..."
   - "Delete skill ..."

### Manual Installation (Alternative)

- Create a new Tool and paste `openwebui_skills_manager.py`.

## Example: Install Skills

This tool can fetch and install skills directly from URLs (supporting GitHub repo roots, tree/blob, raw markdown, and .zip/.tar archives).

### Auto-discover all skills from a GitHub repo

- "Install skills from <https://github.com/nicobailon/visual-explainer>" ← Auto-discovers all subdirectories
- "Install all skills from <https://github.com/anthropics/skills>" ← Installs entire skills directory

### Install a single skill from GitHub

- "Install skill from <https://github.com/anthropics/skills/tree/main/skills/xlsx>"
- "Install skill from <https://github.com/Fu-Jie/openwebui-extensions/blob/main/.agent/skills/test-copilot-pipe/SKILL.md>"

### Batch install multiple skills

- "Install these skills: ['https://github.com/anthropics/skills/tree/main/skills/xlsx', 'https://github.com/anthropics/skills/tree/main/skills/docx']"

> **Tip**: For GitHub, the tool automatically resolves directory (tree) URLs by looking for `SKILL.md`.

## Installation Logic

### URL Type Recognition & Processing

The `install_skill` method automatically detects and handles different URL formats with the following logic:

#### **1. GitHub Repository Root** (Auto-Discovery)

**Format:** `https://github.com/owner/repo` or `https://github.com/owner/repo/`

**Processing:**

1. Detected via regex: `^https://github\.com/([^/]+)/([^/]+)/?$`
2. Automatically converted to: `https://github.com/owner/repo/tree/main`
3. API queries all subdirectories at `/repos/{owner}/{repo}/contents?ref=main`
4. For each subdirectory, creates skill URLs
5. Attempts to fetch `SKILL.md` from each directory
6. All discovered skills installed in **batch mode**

**Example Flow:**

```
Input:  https://github.com/nicobailon/visual-explainer
        ↓ [Detect: repo root]
        ↓ [Convert: add /tree/main]
        ↓ [Query: GitHub API for subdirs]
Discover: skill1, skill2, skill3, ...
        ↓ [Batch mode]
Install: All skills found
```

#### **2. GitHub Tree (Directory) URL** (Auto-Discovery)

**Format:** `https://github.com/owner/repo/tree/branch/path/to/directory`

**Processing:**

1. Detected via regex: `/tree/` in URL
2. API queries directory contents: `/repos/{owner}/{repo}/contents/path?ref=branch`
3. Filters for subdirectories (skips `.hidden` dirs)
4. For each subdirectory, attempts to fetch `SKILL.md`
5. All discovered skills installed in **batch mode**

**Example:**

```
Input:  https://github.com/anthropics/skills/tree/main/skills
        ↓ [Query: /repos/anthropics/skills/contents/skills?ref=main]
Discover: xlsx, docx, pptx, markdown, ...
Install: All 12 skills in batch mode
```

#### **3. GitHub Blob (File) URL** (Single Install)

**Format:** `https://github.com/owner/repo/blob/branch/path/to/SKILL.md`

**Processing:**

1. Detected via pattern: `/blob/` in URL
2. Converted to raw URL: `https://raw.githubusercontent.com/owner/repo/branch/path/to/SKILL.md`
3. Content fetched and parsed as single skill
4. Installed in **single mode**

**Example:**

```
Input:  https://github.com/user/repo/blob/main/SKILL.md
        ↓ [Convert: /blob/ → raw.githubusercontent.com]
        ↓ [Fetch: raw markdown content]
Parse:  Skill name, description, content
Install: Single skill
```

#### **4. Raw GitHub URL** (Single Install)

**Format:** `https://raw.githubusercontent.com/owner/repo/branch/path/to/SKILL.md`

**Processing:**

1. Direct download from raw content endpoint
2. Content parsed as markdown with frontmatter
3. Skill metadata extracted (name, description from frontmatter)
4. Installed in **single mode**

**Example:**

```
Input:  https://raw.githubusercontent.com/Fu-Jie/openwebui-extensions/main/SKILL.md
        ↓ [Fetch: raw content directly]
Parse:  Extract metadata
Install: Single skill
```

#### **5. Archive Files** (Single Install)

**Format:** `https://example.com/skill.zip` or `.tar`, `.tar.gz`, `.tgz`

**Processing:**

1. Detected via file extension: `.zip`, `.tar`, `.tar.gz`, `.tgz`
2. Downloaded and extracted safely:
   - Validates member paths (prevents path traversal attacks)
   - Extracts to temporary directory
3. Searches for `SKILL.md` in archive root
4. Content parsed and installed in **single mode**

**Example:**

```
Input:  https://github.com/user/repo/releases/download/v1.0/my-skill.zip
        ↓ [Download: zip archive]
        ↓ [Extract safely: validate paths]
        ↓ [Search: SKILL.md]
Parse:  Extract metadata
Install: Single skill
```

### Batch Mode vs Single Mode

| Mode | Triggered By | Behavior | Result |
|------|--------------|----------|--------|
| **Batch** | Repo root or tree URL | All subdirectories auto-discovered | List of { succeeded, failed, results } |
| **Single** | Blob, raw, or archive URL | Direct content fetch and parse | { success, id, name, ... } |
| **Batch** | List of URLs | Each URL processed individually | List of results |

### Deduplication During Batch Install

When multiple URLs are provided in batch mode:

1. **URL Deduplication**: Removes duplicate URLs (preserves order)
2. **Name Collision Detection**: Tracks installed skill names
   - If same name appears multiple times → warning notification
   - Action depends on `ALLOW_OVERWRITE_ON_CREATE` valve

**Example:**

```
Input URLs: [url1, url1, url2, url2, url3]
           ↓ [Deduplicate]
Unique:    [url1, url2, url3]
Process:   3 URLs
Output:    "Removed 2 duplicate URL(s)"
```

### Skill Name Resolution

During parsing, skill names are resolved in this order:

1. **User-provided name** (if specified in `name` parameter)
2. **Frontmatter metadata** (from `---` block at file start)
3. **Markdown h1 heading** (first `# Title` found)
4. **Extracted directory/file name** (from URL path)
5. **Fallback name:** `"installed-skill"` (last resort)

**Example:**

```
Markdown document structure:
───────────────────────────
---
title: "My Custom Skill"
description: "Does something useful"
---

# Alternative Title

Content here...
───────────────────────────

Resolution order:
1. Check frontmatter: title = "My Custom Skill" ✓ Use this
2. (Skip other options)

Result: Skill created as "My Custom Skill"
```

### Safety & Security

All installations enforce:

- ✅ **Domain Whitelist** (TRUSTED_DOMAINS): Only github.com, huggingface.co, githubusercontent.com allowed
- ✅ **Scheme Validation**: Only http/https URLs accepted
- ✅ **Path Traversal Prevention**: Archives validated before extraction
- ✅ **User Scope**: Operations isolated per user_id
- ✅ **Timeout Protection**: Configurable timeout (default 12s)

### Error Handling

| Error Case | Handling |
|-----------|----------|
| Unsupported scheme (ftp://, file://) | Blocked at validation |
| Untrusted domain | Rejected (domain not in whitelist) |
| URL fetch timeout | Timeout error with retry suggestion |
| Invalid archive | Error on extraction attempt |
| No SKILL.md found | Error per subdirectory (batch continues) |
| Duplicate skill name | Warning notification (depends on valve) |
| Missing skill name | Error (name is required) |

## Configuration (Valves)

| Parameter | Default | Description |
| --- | --- | --- |
| `SHOW_STATUS` | `True` | Show operation status updates in OpenWebUI status bar. |
| `ALLOW_OVERWRITE_ON_CREATE` | `False` | Allow `create_skill`/`install_skill` to overwrite same-name skill by default. |
| `INSTALL_FETCH_TIMEOUT` | `12.0` | URL fetch timeout in seconds for skill installation. |
| `TRUSTED_DOMAINS` | `github.com,huggingface.co,githubusercontent.com` | Comma-separated list of primary trusted domains for downloads (always enforced). Subdomains automatically allowed (e.g., `github.com` allows `api.github.com`). See [Domain Whitelist Guide](https://github.com/Fu-Jie/openwebui-extensions/blob/main/plugins/tools/openwebui-skills-manager/docs/DOMAIN_WHITELIST.md). |

## Supported Tool Methods

| Method | Purpose |
| --- | --- |
| `list_skills` | List current user's skills. |
| `show_skill` | Show one skill by `skill_id` or `name`. |
| `install_skill` | Install skill from URL into OpenWebUI native skills. |
| `create_skill` | Create a new skill (or overwrite when allowed). |
| `update_skill` | Modify an existing skill by id or name. Update any combination of: `new_name` (rename), `description`, `content`, or `is_active` (enable/disable). Validates name uniqueness. |
| `delete_skill` | Delete a skill by `skill_id` or `name`. |

## Support

If this plugin has been useful, a star on [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions) is a big motivation for me. Thank you for the support.

## Others

- This tool manages OpenWebUI native skill records and supports direct URL installation.
- For advanced orchestration, combine with other Pipe/Tool workflows.

## Changelog

See full history in the GitHub repository releases and commits.
