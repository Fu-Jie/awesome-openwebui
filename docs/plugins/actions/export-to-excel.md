# Export to Excel

<span class="category-badge action">Action</span>
<span class="version-badge">v0.3.11</span>

Export chat conversations to Excel spreadsheet format for analysis, archiving, and sharing.


### What's New in v0.3.11

- **Async DB compatibility on OpenWebUI >= 0.9.0 / v0.10.1**: `_call_db` now uses `iscoroutinefunction` + `asyncio.iscoroutine` to detect whether a DB method is async, instead of relying on `_owui_version_ge("0.9.0")`. In isolated plugin sandboxes the version import can fall back to `"0.0.0"`, which previously caused async DB methods to be called synchronously. This resolves `RuntimeWarning: coroutine '_call_db' was never awaited` and `AttributeError: 'coroutine' object has no attribute 'params'/'email'`. Behavior on OpenWebUI < 0.9.0 is unchanged.

### What's New in v0.3.8
- ⚡ **Open WebUI 0.9.x Compatibility**: Added runtime version detection and async DB call adapters for `Users.get_user_by_id` and `Chats.get_chat_by_id` — ensuring seamless compatibility with Open WebUI 0.9.x.

---


## Overview

The Export to Excel plugin allows you to download your chat conversations as Excel files. This is useful for:

- Archiving important conversations
- Analyzing chat data
- Sharing conversations with colleagues
- Creating documentation from AI-assisted research

## Features

- :material-file-excel: **Excel Export**: Standard `.xlsx` format
- :material-table: **Formatted Output**: Clean table structure
- :material-download: **One-Click Download**: Instant file generation
- :material-history: **Full History**: Exports complete conversation

## Configuration

- **Title Source**: Choose how the filename is generated:
  - `chat_title`: Use the chat title (default).
  - `ai_generated`: Use AI to generate a concise title from the content.
  - `markdown_title`: Extract the first H1/H2 header from the markdown content.

---

## Installation

1. Download the plugin file: [`export_to_excel.py`](https://github.com/Fu-Jie/openwebui-extensions/tree/main/plugins/actions/export_to_excel)
2. Upload to OpenWebUI: **Admin Panel** → **Settings** → **Functions**
3. Enable the plugin

---

## Usage

1. Have a conversation you want to export
2. Click the **Export** button in the message action bar
3. The Excel file will be automatically downloaded

---

## Output Format

The exported Excel file contains:

| Column | Description |
|--------|-------------|
| Timestamp | When the message was sent |
| Role | User or Assistant |
| Content | The message text |
| Model | The AI model used (for assistant messages) |

---

## Requirements

!!! note "Prerequisites"
    - OpenWebUI v0.3.0 or later
    - No additional Python packages required (uses built-in libraries)

---

## Source Code

[:fontawesome-brands-github: View on GitHub](https://github.com/Fu-Jie/openwebui-extensions/tree/main/plugins/actions/export_to_excel){ .md-button }
