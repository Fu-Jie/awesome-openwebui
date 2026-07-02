# 📊 Export to Excel

| By [Fu-Jie](https://github.com/Fu-Jie) · v0.3.10 | [⭐ Star this repo](https://github.com/Fu-Jie/openwebui-extensions) |
| :--- | ---: |

| ![followers](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_followers.json&label=%F0%9F%91%A5&style=flat) | ![points](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_points.json&label=%E2%AD%90&style=flat) | ![top](https://img.shields.io/badge/%F0%9F%8F%86-Top%20%3C1%25-10b981?style=flat) | ![contributions](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_contributions.json&label=%F0%9F%93%A6&style=flat) | ![downloads](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_downloads.json&label=%E2%AC%87%EF%B8%8F&style=flat) | ![saves](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_saves.json&label=%F0%9F%92%BE&style=flat) | ![views](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_views.json&label=%F0%9F%91%81%EF%B8%8F&style=flat) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |

Export chat history to an Excel (.xlsx) file directly from the chat interface.

## Install with Batch Install Plugins

If you already use [Batch Install Plugins from GitHub](https://openwebui.com/posts/batch_install_plugins_install_popular_plugins_in_s_c9fd6e80) , you can install or update this plugin with:

```text
Install plugin from Fu-Jie/openwebui-extensions
```

When the selection dialog opens, search for this plugin, check it, and continue.

> [!IMPORTANT]
> If the official OpenWebUI Community version is already installed, remove it first. After that, Batch Install Plugins can keep this plugin updated in future runs.

## 🔥 What's New in v0.3.9

- 📏 **Configurable Row Height**: Added `ROW_HEIGHT` valve to control data row height. Set to `0` (default) for auto-adjust, or a fixed value (e.g., `20`) for compact single-line rows.
- 📐 **Configurable Column Width**: Added `COLUMN_WIDTH` valve to control column width. Set to `0` (default) for auto-adjust, or a fixed value (e.g., `15`) for uniform compact columns.

## ✨ Core Features

- 🚀 **One-Click Export**: Adds an “Export to Excel” action button to the chat.
- 🧠 **Automatic Header Extraction**: Intelligently identifies table headers from chat content.
- 📊 **Multi-Table Support**: Handles multiple tables within a single chat session.

## 🚀 How to Use

1. **Install**: Search for “Export to Excel” in the Open WebUI Community and install.
2. **Trigger**: In any chat, click the “Export to Excel” action button.
3. **Download**: The .xlsx file will be automatically downloaded.

## ⚙️ Configuration (Valves)

| Parameter | Default | Description |
| :--- | :--- | :--- |
| `TITLE_SOURCE` | `chat_title` | Filename source: `chat_title`, `ai_generated`, or `markdown_title`. |
| `EXPORT_SCOPE` | `last_message` | Export scope: `last_message` or `all_messages`. |
| `MODEL_ID` | `""` | Model ID for AI title generation. Empty uses current chat model. |
| `SHOW_STATUS` | `True` | Show operation status updates. |
| `SHOW_DEBUG_LOG` | `False` | Print debug logs in the browser console (F12). |
| `ROW_HEIGHT` | `0` | Fixed row height in points. `0` = auto-adjust based on content. Set e.g. `20` for compact rows. |
| `COLUMN_WIDTH` | `0` | Fixed column width in characters. `0` = auto-adjust based on content. Set e.g. `15` for uniform compact columns. |

## ⭐ Support

If this plugin has been useful, a star on [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions) is a big motivation for me. Thank you for the support.

## Troubleshooting ❓

- **Plugin not working?**: Check if the filter/action is enabled in the model settings.
- **Debug Logs**: Enable `SHOW_STATUS` and check the browser console (F12) if needed.
- **Error Messages**: If you see an error, please copy the full error message and report it.
- **Submit an Issue**: If you encounter any problems, please submit an issue on GitHub: [OpenWebUI Extensions Issues](https://github.com/Fu-Jie/openwebui-extensions/issues)

## Changelog

See the full history on GitHub: [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions)# Export to Excel

This plugin allows you to export your chat history to an Excel (.xlsx) file directly from the chat interface.

## What's New in v0.3.6

- **OpenWebUI-Style Theme**: Modern dark header (#1f2937) with light gray zebra striping for better readability.
- **Zebra Striping**: Alternating row colors (#ffffff / #f3f4f6) for improved visual scanning.
- **Smart Data Type Conversion**: Automatically converts columns to numeric or datetime types with fallback to string.
- **Full Cell Bold/Italic**: Supports full cell Markdown bold (`**text**`) and italic (`*text*`) formatting in Excel.
- **Partial Markdown Cleanup**: Automatically removes partial Markdown formatting symbols (e.g., `Some **bold** text` → `Some bold text`) for cleaner Excel output.
- **Export Scope**: Added `EXPORT_SCOPE` valve to choose between exporting tables from the "Last Message" (default) or "All Messages".
- **Smart Sheet Naming**: Automatically names sheets based on Markdown headers, AI titles (if enabled), or message index (e.g., `Msg1-Tab1`).
- **Multiple Tables Support**: Improved handling of multiple tables within single or multiple messages.
- **Smart Filename Generation**: Supports generating filenames based on Chat Title, AI Summary, or Markdown Headers.
- **Configuration Options**: Added `TITLE_SOURCE` setting to control filename generation strategy.
- **AI Title Generation**: Added `MODEL_ID` setting to specify the model for AI title generation, with progress notifications.

## Features

- **One-Click Export**: Adds an "Export to Excel" button to the chat.
- **Automatic Header Extraction**: Intelligently identifies table headers from the chat content.
- **Multi-Table Support**: Handles multiple tables within a single chat session.

## Configuration

- **Title Source**: Choose how the filename is generated:
  - `chat_title`: Use the chat title (default).
  - `ai_generated`: Use AI to generate a concise title from the content.
  - `markdown_title`: Extract the first H1/H2 header from the markdown content.

## Usage

1. Install the plugin.
2. In any chat, click the "Export to Excel" button.
3. The file will be automatically downloaded to your device.

## Author

Fu-Jie
GitHub: [Fu-Jie/openwebui-extensions](https://github.com/Fu-Jie/openwebui-extensions)

## License

MIT License
