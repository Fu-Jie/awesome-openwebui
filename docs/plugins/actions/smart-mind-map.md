# Smart Mind Map - Mind Mapping Generation Plugin

Smart Mind Map is a powerful OpenWebUI action plugin that intelligently analyzes long-form text content and automatically generates interactive mind maps, helping users structure and visualize knowledge.

| By [Fu-Jie](https://github.com/Fu-Jie) · v1.0.3 | [⭐ Star this repo](https://github.com/Fu-Jie/openwebui-extensions) |
| :--- | ---: |

| ![followers](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_followers.json&label=%F0%9F%91%A5&style=flat) | ![points](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_points.json&label=%E2%AD%90&style=flat) | ![top](https://img.shields.io/badge/%F0%9F%8F%86-Top%20%3C1%25-10b981?style=flat) | ![contributions](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_contributions.json&label=%F0%9F%93%A6&style=flat) | ![downloads](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_downloads.json&label=%E2%AC%87%EF%B8%8F&style=flat) | ![saves](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_saves.json&label=%F0%9F%92%BE&style=flat) | ![views](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_views.json&label=%F0%9F%91%81%EF%B8%8F&style=flat) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |

> 🏆 **Featured by OpenWebUI Official** — This plugin was recommended in the official OpenWebUI Community Newsletter: [February 3, 2026](https://openwebui.com/blog/open-webui-community-newsletter-february-3rd-2026)

## Install with Batch Install Plugins

If you already use [Batch Install Plugins from GitHub](https://openwebui.com/posts/batch_install_plugins_install_popular_plugins_in_s_c9fd6e80) , you can install or update this plugin with:

```text
Install plugin from Fu-Jie/openwebui-extensions
```

When the selection dialog opens, search for this plugin, check it, and continue.

> [!IMPORTANT]
> If the official OpenWebUI Community version is already installed, remove it first. After that, Batch Install Plugins can keep this plugin updated in future runs.

## What's New in v1.0.3

- **Async DB compatibility on OpenWebUI >= 0.9.0 / v0.10.1**: `_call_db` now uses `iscoroutinefunction` + `asyncio.iscoroutine` to detect whether a DB method is async, instead of relying on `_owui_version_ge("0.9.0")`. In isolated plugin sandboxes the version import can fall back to `"0.0.0"`, which previously caused async DB methods to be called synchronously. This resolves `RuntimeWarning: coroutine '_call_db' was never awaited` and `AttributeError: 'coroutine' object has no attribute 'params'/'email'`. Behavior on OpenWebUI < 0.9.0 is unchanged.

## What's New in v1.0.2

### OpenWebUI v0.10+ Compatibility Fix (issue #101)

- **Frontend crash fixed**: The action no longer appends an id-less message on early-return paths, which caused `Cannot read properties of undefined (reading 'content')` in OWUI v0.10+'s `chatActionHandler`. The existing last message is updated in place instead.
- **Empty content recovered**: OWUI v0.10+ stores assistant replies in a structured `output` field and leaves `content` empty. The plugin now rebuilds the text from `output` via OWUI's `convert_output_to_messages` (reasoning excluded), with a DB-lookup fallback via `ChatMessages.get_message_by_id`.
- **Minimum OWUI declared**: `required_open_webui_version: 0.10.2` is now in the metadata. On older OWUI, install [v1.0.1](https://github.com/Fu-Jie/openwebui-extensions/releases/tag/smart-mind-map-v1.0.1) instead.

## Key Features 🔑

- ✅ **Intelligent Text Analysis**: Automatically identifies core themes, key concepts, and hierarchical structures.
- ✅ **Native Multi-language UI**: Automatic interface translation (i18n) based on system language for a native feel.
- ✅ **Interactive Visualization**: Generates beautiful interactive mind maps based on Markmap.js.
- ✅ **Direct Embed Mode**: (Optional) For Open WebUI 0.8.0+, render natively inline to fill entire UI width.
- ✅ **High-Resolution PNG Export**: Export mind maps as high-quality PNG images (9x scale).
- ✅ **Complete Control Panel**: Zoom controls, expand level selection, and fullscreen mode within a compact toolbar.
- ✅ **Theme Switching**: Manual theme toggle button with automatic theme detection.
- ✅ **Image Output Mode**: Generate static SVG images embedded directly in Markdown for cleaner history.

## How to Use 🛠️

1. **Install**: Upload the `smart_mind_map.py` file in OpenWebUI Admin Settings -> Plugins -> Actions.
2. **Configure**: Ensure you have an LLM model configured (e.g., `gemini-2.5-flash`).
3. **Trigger**: Enable the "Smart Mind Map" action in chat settings and send text (at least 100 characters).
4. **Result**: The mind map will be rendered directly in the chat interface.

## Configuration (Valves) ⚙️

| Parameter | Default | Description |
| :--- | :--- | :--- |
| `show_status` | `true` | Whether to display operation status updates. |
| `LLM_MODEL_ID` | `gemini-2.5-flash` | LLM model ID for text analysis. |
| `MIN_TEXT_LENGTH` | `100` | Minimum text length required for analysis. |
| `CLEAR_PREVIOUS_HTML` | `false` | Whether to clear previous plugin-generated HTML content. |
| `MESSAGE_COUNT` | `1` | Number of recent messages to use for generation (1-5). |
| `OUTPUT_MODE` | `html` | Output mode: `html` (interactive) or `image` (static). |
| `ENABLE_DIRECT_EMBED_MODE` | `false` | Enable Direct Embed Mode (Open WebUI 0.8.0+ native layout) instead of Legacy Mode. |

## ⭐ Support

If this plugin has been useful, a star on [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions) is a big motivation for me. Thank you for the support.

## Troubleshooting ❓

- **Plugin not working?**: Check if the action is enabled in the chat settings.
- **Text too short**: Ensure input text contains at least 100 characters.
- **Rendering failed**: Check browser console for errors related to Markmap.js or D3.js.
- **Submit an Issue**: If you encounter any problems, please submit an issue on GitHub: [OpenWebUI Extensions Issues](https://github.com/Fu-Jie/openwebui-extensions/issues)

---

## Technical Architecture

- **Markmap.js**: Open-source mind mapping rendering engine.
- **PNG Export**: 9x scale factor for print-quality output (~1-2MB file size).
- **Theme Detection**: 4-level priority detection (Manual > Meta > Class > System).
- **Security**: XSS protection and input validation.

## Best Practices

1. **Text Preparation**: Provide text with clear structure and distinct hierarchies.
2. **Model Selection**: Use fast models like `gemini-2.5-flash` for daily use.
3. **Export Quality**: Use PNG for presentations and SVG for further editing.

## Changelog

See the full history on GitHub: [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions)
