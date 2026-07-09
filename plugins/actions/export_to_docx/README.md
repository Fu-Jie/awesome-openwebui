# 📝 Export to Word (Enhanced)

| By [Fu-Jie](https://github.com/Fu-Jie) · v0.5.2 | [⭐ Star this repo](https://github.com/Fu-Jie/openwebui-extensions) |
| :--- | ---: |

| ![followers](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_followers.json&label=%F0%9F%91%A5&style=flat) | ![points](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_points.json&label=%E2%AD%90&style=flat) | ![top](https://img.shields.io/badge/%F0%9F%8F%86-Top%20%3C1%25-10b981?style=flat) | ![contributions](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_contributions.json&label=%F0%9F%93%A6&style=flat) | ![downloads](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_downloads.json&label=%E2%AC%87%EF%B8%8F&style=flat) | ![saves](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_saves.json&label=%F0%9F%92%BE&style=flat) | ![views](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_views.json&label=%F0%9F%91%81%EF%B8%8F&style=flat) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |

Export conversation to Word (.docx) with **syntax highlighting**, **native math equations**, **Mermaid diagrams**, **citations**, and **enhanced table formatting**.

## Install with Batch Install Plugins

If you already use [Batch Install Plugins from GitHub](https://openwebui.com/posts/batch_install_plugins_install_popular_plugins_in_s_c9fd6e80) , you can install or update this plugin with:

```text
Install plugin from Fu-Jie/openwebui-extensions
```

When the selection dialog opens, search for this plugin, check it, and continue.

> [!IMPORTANT]
> If the official OpenWebUI Community version is already installed, remove it first. After that, Batch Install Plugins can keep this plugin updated in future runs.

## 🔥 What's New in v0.5.2

- 📊 **Mermaid Diagrams with `<br>` Labels**: Diagrams whose labels contain `<br>` line breaks exported as a blank square. Mermaid 11 emits `<foreignObject>` HTML labels even with the per-diagram `htmlLabels:false`, and an unclosed `<br>` makes the SVG invalid XML — so it fails to rasterize to PNG. Setting `htmlLabels:false` at the **top level** of `mermaid.initialize` suppresses `<foreignObject>` entirely; labels render as native SVG text and diagrams rasterize correctly.

<details>
<summary>v0.5.1 changes</summary>

- 🛠️ **Open WebUI 0.10.x Compatibility (Critical)**: OWUI 0.10 moved assistant replies into a structured `output` field and left `content` empty, breaking export with "No content found to export!". Assistant text is now recovered via `ChatMessages` + `convert_output_to_messages` (OpenWebUI-native, reasoning excluded). **Requires OWUI ≥ 0.10.2.**
- 🖼️ **Unified Storage for File Images**: Replaced the hand-rolled `boto3`/S3 + multi-path disk fallbacks with OpenWebUI's `Storage` provider — local/S3/GCS/Azure all work via OWUI's own storage config. **`boto3` dependency dropped.**
- 🌐 **Opt-in External Image Embedding**: New `EMBED_EXTERNAL_IMAGES` valve (off by default) downloads and embeds `![](https://…)` images, fetched through OWUI's SSRF-safe `validate_url` + `get_ssrf_safe_session`, capped by `MAX_EMBED_IMAGE_MB`.
- 🧹 **Reference-Definition Stripping**: Markdown `[label]: target` lines (invisible in chat) are now stripped from the export, matching OpenWebUI's `removeFormattings`.

</details>

<details>
<summary>v0.5.0 changes</summary>

- 🔠 **Heading-Level Font Customization**: New `FONT_H1_LATIN`, `FONT_H1_ASIAN`, `FONT_H2_LATIN`, `FONT_H2_ASIAN` valves — configure H1 and H2 fonts independently from body text.
- ⬆️ **Relative Heading Algorithm**: When content has no H1, heading levels are automatically promoted (e.g., `## → #`) so the document hierarchy stays correct.
- 🧹 **Metadata Sanitization**: Word document properties (`author`, `last_modified_by`, etc.) now use the real user name instead of exposing `python-docx` library fingerprints.
- 🎨 **Heading Style Fixes**: Cleared Word theme font inheritance (`w:asciiTheme`, `w:eastAsiaTheme`) on Title, Heading 1-9, and default styles to prevent Word from overriding custom fonts (e.g., SimSun fallback). Removed spurious underlines and borders from heading styles.

</details>

## ✨ Key Features

- 🚀 **One-Click Export**: Adds an "Export to Word" action button to the chat.
- 📄 **Markdown Conversion**: Full Markdown syntax support (headings, bold, italic, code, tables, lists).
- 🎨 **Syntax Highlighting**: Code blocks highlighted with Pygments (500+ languages).
- 🔢 **Native Math Equations**: LaTeX math (`$$...$$`, `\[...\]`, `$...$`) converted to editable Word equations.
- 📊 **Mermaid Diagrams**: Flowcharts and sequence diagrams rendered as images.
- 📚 **Citations & References**: Auto-generates References section with clickable citation links.
- 🧹 **Reasoning Stripping**: Automatically removes AI thinking blocks (`<think>`, `<analysis>`).
- 📋 **Enhanced Tables**: Smart column widths, alignment, header row repeat across pages.
- 💬 **Blockquote Support**: Markdown blockquotes with left border and gray styling.
- 🌐 **Multi-language Support**: Proper handling of Chinese and English text.

## 🚀 How to Use

1. **Install**: Search for "Export to Word" in the Open WebUI Community and install.
2. **Trigger**: In any chat, click the "Export to Word" action button.
3. **Download**: The .docx file will be automatically downloaded.

## ⚙️ Configuration (Valves)

| Parameter | Default | Description |
| :--- | :--- | :--- |
| **Title Source (TITLE_SOURCE)** | `chat_title` | `chat_title`, `ai_generated`, or `markdown_title` |
| **Max Image Size (MAX_EMBED_IMAGE_MB)** | `20` | Maximum image size to embed (MB) |
| **Embed External Images (EMBED_EXTERNAL_IMAGES)** | `False` | Download and embed `![](https://…)` images into the .docx (SSRF-safe, capped by `MAX_EMBED_IMAGE_MB`) |
| **UI Language (UI_LANGUAGE)** | `en` | `en` (English) or `zh` (Chinese) |
| **Latin Font (FONT_LATIN)** | `Times New Roman` | Font for Latin characters |
| **Asian Font (FONT_ASIAN)** | `SimSun` | Font for Asian characters |
| **Code Font (FONT_CODE)** | `Consolas` | Font for code blocks |
| **H1 Latin Font (FONT_H1_LATIN)** | `Aptos Display` | Font for Heading 1 Latin characters |
| **H1 Asian Font (FONT_H1_ASIAN)** | `SimHei` | Font for Heading 1 Asian characters |
| **H2 Latin Font (FONT_H2_LATIN)** | `Calibri Light` | Font for Heading 2 Latin characters |
| **H2 Asian Font (FONT_H2_ASIAN)** | `SimHei` | Font for Heading 2 Asian characters |
| **Table Header Color** | `F2F2F2` | Header background color (hex) |
| **Table Zebra Color** | `FBFBFB` | Alternating row color (hex) |
| **Mermaid PNG Scale** | `3.0` | Resolution multiplier for Mermaid images |
| **Math Enable** | `True` | Enable LaTeX math conversion |

## ⭐ Support

If this plugin has been useful, a star on [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions) is a big motivation for me. Thank you for the support.

## 🛠️ Supported Markdown Syntax

| Syntax | Word Result |
| :--- | :--- |
| `# Heading 1` to `###### Heading 6` | Heading levels 1-6 |
| `**bold**` or `__bold__` | Bold text |
| `*italic*` or `_italic_` | Italic text |
| `` `inline code` `` | Monospace with gray background |
| ` ``` code block ``` ` | **Syntax highlighted** code block |
| `> blockquote` | Left-bordered gray italic text |
| `[link](url)` | Blue underlined link |
| `~~strikethrough~~` | Strikethrough text |
| `- item` or `* item` | Bullet list |
| `1. item` | Numbered list |
| Markdown tables | **Enhanced table** with smart widths |
| `$$LaTeX$$` or `\[LaTeX\]` | **Native Word equation** (display) |
| `$LaTeX$` or `\(LaTeX\)` | **Native Word equation** (inline) |
| ` ```mermaid ... ``` ` | **Mermaid diagram** as image |
| `[1]` citation markers | **Clickable links** to References |

## 📦 Requirements

- `python-docx==1.1.2` - Word document generation
- `Pygments>=2.15.0` - Syntax highlighting
- `latex2mathml` - LaTeX to MathML conversion
- `mathml2omml` - MathML to Office Math (OMML) conversion

## Troubleshooting ❓

- **Plugin not working?**: Check if the filter/action is enabled in the model settings.
- **Debug Logs**: Check the browser console (F12) for detailed logs if available.
- **Error Messages**: If you see an error, please copy the full error message and report it.
- **Submit an Issue**: If you encounter any problems, please submit an issue on GitHub: [OpenWebUI Extensions Issues](https://github.com/Fu-Jie/openwebui-extensions/issues)

## 📝 Changelog

See the full history on GitHub: [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions)
