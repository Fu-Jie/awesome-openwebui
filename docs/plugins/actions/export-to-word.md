# Export to Word

<span class="category-badge action">Action</span>
<span class="version-badge">v0.5.3</span>

Export conversation to Word (.docx) with **syntax highlighting**, **native math equations**, **Mermaid diagrams**, **citations**, and **enhanced table formatting**.

---

## Overview

The Export to Word plugin converts chat messages from Markdown to a polished Word document. It handles headings, lists, tables, code blocks, and blockquotes while keeping both English and Chinese text rendering clean.

## Features

- :material-file-word-box: **One-Click Export**: Adds an "Export to Word" action button to the chat.
- :material-format-bold: **Markdown Conversion**: Converts Markdown syntax to Word formatting (headings, bold, italic, code, tables, lists).
- :material-code-tags: **Syntax Highlighting**: Code blocks are highlighted with Pygments (supports 500+ languages).
- :material-sigma: **Native Math Equations**: LaTeX math (`$$...$$`, `\[...\]`, `$...$`, `\(...\)`) converted to editable Word equations.
- :material-graph: **Mermaid Diagrams**: Mermaid flowcharts and sequence diagrams rendered as images in the document.
- :material-book-open-page-variant: **Citations & References**: Auto-generates a References section from OpenWebUI sources with clickable citation links.
- :material-brain-off: **Reasoning Stripping**: Automatically removes AI thinking blocks (`<think>`, `<analysis>`) from exports.
- :material-table: **Enhanced Tables**: Smart column widths, column alignment (`:---`, `---:`, `:---:`), header row repeat across pages.
- :material-format-quote-close: **Blockquote Support**: Markdown blockquotes are rendered with left border and gray styling.
- :material-translate: **Multi-language Support**: Properly handles both Chinese and English text.
- :material-file-document-outline: **Smarter Filenames**: Configurable title source (Chat Title, AI Generated, or Markdown Title).

---

## Configuration

You can configure the following settings via the **Valves** button in the plugin settings:

| Valve | Description | Default |
| :--- | :--- | :--- |
| `TITLE_SOURCE` | Source for document title/filename. Options: `chat_title`, `ai_generated`, `markdown_title` | `chat_title` |
| `MAX_EMBED_IMAGE_MB` | Maximum image size to embed into DOCX (MB). | `20` |
| `UI_LANGUAGE` | User interface language. Options: `en` (English), `zh` (Chinese). | `en` |
| `FONT_LATIN` | Font name for Latin characters. | `Times New Roman` |
| `FONT_ASIAN` | Font name for Asian characters. | `SimSun` |
| `FONT_CODE` | Font name for code blocks. | `Consolas` |
| `FONT_H1_LATIN` | Font for Heading 1 Latin characters. | `Aptos Display` |
| `FONT_H1_ASIAN` | Font for Heading 1 Asian characters. | `SimHei` |
| `FONT_H2_LATIN` | Font for Heading 2 Latin characters. | `Calibri Light` |
| `FONT_H2_ASIAN` | Font for Heading 2 Asian characters. | `SimHei` |
| `TABLE_HEADER_COLOR` | Table header background color (Hex without #). | `F2F2F2` |
| `TABLE_ZEBRA_COLOR` | Table alternating row background color (Hex without #). | `FBFBFB` |
| `MERMAID_JS_URL` | URL for the Mermaid.js library. | `https://cdn.jsdelivr.net/npm/mermaid@11.12.2/dist/mermaid.min.js` |
| `MERMAID_JSZIP_URL` | URL for the JSZip library (required for DOCX manipulation). | `https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js` |
| `MERMAID_PNG_SCALE` | Scale factor for Mermaid PNG generation (Resolution). | `3.0` |
| `MERMAID_DISPLAY_SCALE` | Scale factor for Mermaid visual size in Word. | `1.0` |
| `MERMAID_OPTIMIZE_LAYOUT` | Automatically convert LR (Left-Right) flowcharts to TD (Top-Down). | `False` |
| `MERMAID_BACKGROUND` | Background color for Mermaid diagrams (e.g., `white`, `transparent`). | `transparent` |
| `MERMAID_CAPTIONS_ENABLE` | Enable/disable figure captions for Mermaid diagrams. | `True` |
| `MERMAID_CAPTION_STYLE` | Paragraph style name for Mermaid captions. | `Caption` |
| `MERMAID_CAPTION_PREF5.0

- 🔠 **Heading-Level Font Customization**: New `FONT_H1_LATIN`, `FONT_H1_ASIAN`, `FONT_H2_LATIN`, `FONT_H2_ASIAN` valves — configure H1 and H2 fonts independently from body text.
- ⬆️ **Relative Heading Algorithm**: When content has no H1, heading levels are automatically promoted (e.g., `## → #`) so the document hierarchy stays correct.
- 🧹 **Metadata Sanitization**: Word document properties (`author`, `last_modified_by`, etc.) now use the real user name instead of exposing `python-docx` library fingerprints.
- 🎨 **Heading Style Fixes**: Cleared Word theme font inheritance (`w:asciiTheme`, `w:eastAsiaTheme`) on Title, Heading 1-9, and default styles to prevent Word from overriding custom fonts (e.g., SimSun fallback). Removed spurious underlines and borders from heading styles
- 🧹 **Content Cleanup**: Enhanced stripping of `<details>` blocks (often used for tool calls/thinking process) to ensure a clean final document.
- 📄 **Standard Document Formatting**: Applied professional document formatting standards for titles and headings (centered title, bold, optimized font sizes and spacing), including GB/T compliance for Chinese content.
- 🔠 **Font Rendering Fix**: Fixed an issue where CJK characters would fallback to MS Gothic in Word; now correctly uses the configured Asian font (e.g., SimSun).
- ⚙️ **Title Alignment**: Added `TITLE_ALIGNMENT` valve to configure document title alignment (left, center, right).

### User-Level Configuration (UserValves)

Users can override the following settings in their personal settings:

- `TITLE_SOURCE`
- `UI_LANGUAGE`
- `FONT_LATIN`, `FONT_ASIAN`, `FONT_CODE`
- `TABLE_HEADER_COLOR`, `TABLE_ZEBRA_COLOR`
- `MERMAID_...` (Selected Mermaid settings)
- `MATH_...` (Math settings)

---

## Installation

1. Download the plugin file: [`export_to_word.py`](https://github.com/Fu-Jie/openwebui-extensions/tree/main/plugins/actions/export_to_docx)
2. Upload to OpenWebUI: **Admin Panel** → **Settings** → **Functions**
3. Enable the plugin

---

## Usage

1. Open the conversation you want to export
2. Click the **Export to Word** button in the message action bar
3. The `.docx` file will download automatically

---

## Supported Markdown Syntax

| Syntax | Word Result |
| :--- | :--- |
| `# Heading 1` to `###### Heading 6` | Heading levels 1-6 |
| `**bold**` or `__bold__` | Bold text |
| `*italic*` or `_italic_` | Italic text |
| `***bold italic***` | Bold + Italic |
| `` `inline code` `` | Monospace with gray background |
| ` ``` code block ``` ` | **Syntax highlighted** code block |
| `> blockquote` | Left-bordered gray italic text |
| `[link](url)` | Blue underlined link text |
| `~~strikethrough~~` | Strikethrough text |
| `- item` or `* item` | Bullet list |
| `1. item` | Numbered list |
| Markdown tables | **Enhanced table** with smart widths |
| `---` or `***` | Horizontal rule |
| `$$LaTeX$$` or `\[LaTeX\]` | **Native Word equation** (display) |
| `$LaTeX$` or `\(LaTeX\)` | **Native Word equation** (inline) |
| ` ```mermaid ... ``` ` | **Mermaid diagram** as image |
| `[1]` citation markers | **Clickable links** to References |

---

## Requirements

!!! note "Prerequisites"
    - `python-docx==1.1.2` - Word document generation
    - `Pygments>=2.15.0` - Syntax highlighting
    - `latex2mathml` - LaTeX to MathML conversion
    - `mathml2omml` - MathML to Office Math (OMML) conversion

---
5.0
## Source Code

[:fontawesome-brands-github: View on GitHub](https://github.com/Fu-Jie/openwebui-extensions/tree/main/plugins/actions/export_to_docx){ .md-button }
**Author:** [Fu-Jie](https://github.com/Fu-Jie) | **Version:** 0.4.4 | **Project:** [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions)
