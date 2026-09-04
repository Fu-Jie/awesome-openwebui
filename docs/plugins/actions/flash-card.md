# Flash Card

Generate polished learning flashcards from any text—title, summary, key points, tags, and category—ready for review and sharing.

| By [Fu-Jie](https://github.com/Fu-Jie) · v0.2.6 | [⭐ Star this repo](https://github.com/Fu-Jie/openwebui-extensions) |
| :--- | ---: |

| ![followers](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_followers.json&label=%F0%9F%91%A5&style=flat) | ![points](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_points.json&label=%E2%AD%90&style=flat) | ![top](https://img.shields.io/badge/%F0%9F%8F%86-Top%20%3C1%25-10b981?style=flat) | ![contributions](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_contributions.json&label=%F0%9F%93%A6&style=flat) | ![downloads](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_downloads.json&label=%E2%AC%87%EF%B8%8F&style=flat) | ![saves](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_saves.json&label=%F0%9F%92%BE&style=flat) | ![views](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_views.json&label=%F0%9F%91%81%EF%B8%8F&style=flat) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |

## Install with Batch Install Plugins

If you already use [Batch Install Plugins from GitHub](https://openwebui.com/posts/batch_install_plugins_install_popular_plugins_in_s_c9fd6e80) , you can install or update this plugin with:

```text
Install plugin from Fu-Jie/openwebui-extensions
```

When the selection dialog opens, search for this plugin, check it, and continue.

> [!IMPORTANT]
> If the official OpenWebUI Community version is already installed, remove it first. After that, Batch Install Plugins can keep this plugin updated in future runs.

## What's New in v0.2.6

- **OpenWebUI 0.11+ Rich UI compatibility**: Successful generations now return an inline `HTMLResponse`, allowing OpenWebUI to emit the generated card as a Rich UI embed.
- **Reliable rendering**: Removed the fenced-HTML message mutation that newer OpenWebUI versions no longer persist or render.

## Key Features 🔑

- **One-click generation**: Drop in text, get a structured card.
- **Concise extraction**: 3–5 key points and 2–4 tags automatically surfaced.
- **Multi-language**: Choose target language (default English).
- **Progressive merge**: Multiple runs append cards into the same HTML container; enable clearing to reset.
- **Status updates**: Live notifications for generating/done/error.

## How to Use 🛠️

1. **Install**: Add the plugin to your OpenWebUI instance.
2. **Configure**: Adjust settings in the Valves menu (optional).
3. **Trigger**: Send text to the chat.
4. **Result**: Watch status updates; the generated card is rendered as an inline Rich UI embed.

## Configuration (Valves) ⚙️

| Param               | Description                                                  | Default |
| ------------------- | ------------------------------------------------------------ | ------- |
| MODEL_ID            | Model to use; empty falls back to current session model      | empty   |
| MIN_TEXT_LENGTH     | Minimum text length; below this prompts for more text        | 50      |
| LANGUAGE            | Output language (e.g., en, zh)                               | en      |
| SHOW_STATUS         | Whether to show status updates                               | true    |
| CLEAR_PREVIOUS_HTML | Whether to clear previous card HTML (otherwise append/merge) | false   |
| MESSAGE_COUNT       | Use the latest N messages to build the card                  | 1       |

## ⭐ Support

If this plugin has been useful, a star on [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions) is a big motivation for me. Thank you for the support.

## Troubleshooting ❓

- **Plugin not working?**: Check if the filter/action is enabled in the model settings.
- **Debug Logs**: Enable `SHOW_STATUS` in Valves to see progress updates.
- **Error Messages**: If you see an error, please copy the full error message and report it.
- **Submit an Issue**: If you encounter any problems, please submit an issue on GitHub: [OpenWebUI Extensions Issues](https://github.com/Fu-Jie/openwebui-extensions/issues)

## Preview 📸

![Flash Card Example](https://raw.githubusercontent.com/Fu-Jie/openwebui-extensions/main/plugins/actions/flash-card/flash_card.png)

## Changelog

See the full history on GitHub: [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions)
