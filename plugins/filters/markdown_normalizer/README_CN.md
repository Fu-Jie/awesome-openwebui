# Markdown 格式化过滤器 (Markdown Normalizer)

| 作者：[Fu-Jie](https://github.com/Fu-Jie) · v1.2.9 | [⭐ 点个 Star 支持项目](https://github.com/Fu-Jie/openwebui-extensions) |
| :--- | ---: |

| ![followers](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_followers.json&label=%F0%9F%91%A5&style=flat) | ![points](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_points.json&label=%E2%AD%90&style=flat) | ![top](https://img.shields.io/badge/%F0%9F%8F%86-Top%20%3C1%25-10b981?style=flat) | ![contributions](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_contributions.json&label=%F0%9F%93%A6&style=flat) | ![downloads](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_downloads.json&label=%E2%AC%87%EF%B8%8F&style=flat) | ![saves](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_saves.json&label=%F0%9F%92%BE&style=flat) | ![views](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_views.json&label=%F0%9F%91%81%EF%B8%8F&style=flat) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |

这是一个强大的、具备上下文感知的 Markdown 内容规范化过滤器，专为 Open WebUI 设计，旨在实时修复大语言模型 (LLM) 输出中常见的格式错乱问题。它能确保代码块、LaTeX 公式、Mermaid 图表以及其他结构化元素被完美渲染，同时**绝不破坏**你原有的有效技术内容（如代码、正则、路径）。

> 🏆 **OpenWebUI 官方推荐** — 本插件获得 OpenWebUI 社区 Newsletter 官方推荐：[2026 年 1 月 28 日](https://openwebui.com/blog/newsletter-january-28-2026)

[English](https://github.com/Fu-Jie/openwebui-extensions/blob/main/plugins/filters/markdown_normalizer/README.md) | [简体中文](https://github.com/Fu-Jie/openwebui-extensions/blob/main/plugins/filters/markdown_normalizer/README_CN.md)

---

## 使用 Batch Install Plugins 安装

如果你已经安装了 [Batch Install Plugins from GitHub](https://openwebui.com/posts/batch_install_plugins_install_popular_plugins_in_s_c9fd6e80) ，可以用下面这句来安装或更新当前插件：

```text
从 Fu-Jie/openwebui-extensions 安装插件
```

当选择弹窗打开后，搜索当前插件，勾选后继续安装即可。

> [!IMPORTANT]
> 如果你已经安装了 OpenWebUI 官方社区里的同名版本，请先删除旧版本，否则重新安装时可能报错。删除后，Batch Install Plugins 后续就可以继续负责更新这个插件。

## 🔥 最新更新 v1.2.9

* **词内强调修复 (issue [#97](https://github.com/Fu-Jie/openwebui-extensions/issues/97))**：新增 `enable_intra_word_emphasis_fix` 配置项。当 LLM 在词边界内标记仅含标点的添加时——例如 `series**,**`（添加的逗号用粗体）或 `word~~,~~`（添加的删除线）——大多数 Markdown 解析器会因为开头定界符位于词内而拒绝渲染该强调。插件现在会将开头标记移动到词的开头（`series**,**` → `**series,**`），让添加的标点能与单词一起渲染。非常适合语法/拼写差异输出。仅对包含纯标点内容的情况进行转换，因此合法的 `**bold**` / `word**bold**` 标记不会被改动。默认关闭。

## 🔥 最新更新 v1.2.8

* **“默认安全”策略 (Safe-by-Default)**：`enable_escape_fix` 功能现在**默认禁用**。这能有效防止插件在未经授权的情况下误改 Windows 路径 (`C:\new\test`) 或复杂的 LaTeX 公式。
* **LaTeX 解析优化**：重构了显示数学公式 (`$$ ... $$`) 的识别逻辑。修复了 LaTeX 命令如果以 `\n` 开头（如 `\nabla`）会被错误识别为换行符的 Bug。
* **可靠性增强**：实现了完整的错误回滚机制。当修复过程发生意外错误时，保证 100% 返回原始文本，不丢失任何数据。
* **配置项修复**：`enable_escape_fix_in_code_blocks` 配置项现在能正确作用于代码块了。**如果您遇到 SQL 挤在一行的问题，只需在设置中手动开启此项即可。**

---

## 🚀 为什么你需要这个插件？(它能解决什么问题？)

由于分词 (Tokenization) 伪影、过度转义或格式幻觉，LLM 经常会生成破损的 Markdown。如果你遇到过以下情况：
* `mermaid` 图表因为节点标签缺少双引号而渲染失败、白屏。
* LLM 输出的 SQL 语句挤在一行，因为本该换行的地方输出了字面量 `\n`。
* 复杂的 `<details>` (思维链展开块) 因为缺少换行符导致整个聊天界面排版崩塌。
* LaTeX 数学公式无法显示，因为模型使用了旧版的 `\[` 而不是 Markdown 支持的 `$$`。

**本插件会自动拦截 LLM 返回的原始数据，实时分析其文本结构，并像外科手术一样精准修复这些排版错误，然后再将其展示在你的浏览器中。**

## ✨ 核心功能与修复能力全景

### 1. 高级结构保护 (上下文感知)

在执行任何修改前，插件会为整个文本建立语义地图，确保技术性内容不被误伤：
* **代码块保护**：默认跳过 ` ``` ` 内部的内容，保护所有编程逻辑。
* **行内代码保护**：识别 `` `代码` `` 片段，防止正则表达式（如 `[\n\r]`）或文件路径（如 `C:\Windows`）被错误地去转义。
* **LaTeX 公式保护**：识别行内 (`$`) 和块级 (`$$`) 公式，防止诸如 `\times`, `\theta` 等核心数学命令被意外破坏。

### 2. 自动治愈转换 (Auto-Healing)

- **Details 标签排版修复**：`<details>` 块要求极为严格的空行才能正确渲染内部内容。插件会自动在 `</details>` 以及自闭合 `<details />` 标签后注入安全的换行符。
* **Mermaid 语法急救**：自动修复最常见的 Mermaid 错误——为未加引号的节点标签（如 `A --> B(Some text)`）自动补充双引号，甚至支持多行标签和引用，确保拓扑图 100% 渲染。
* **强调语法间距修复**：修复加粗/斜体语法内部多余的空格（如 `** 文本 **` 变为 `**文本**`，否则 OpenWebUI 无法加粗），同时智能忽略数学算式（如 `2 * 3 * 4`）。
* **词内强调修复**：当 LLM 在词边界内标记仅含标点的添加时（如 `series**,**` 表示添加了逗号），大多数解析器会拒绝渲染该强调。插件会将开头标记移动到词的开头（`series**,**` → `**series,**`），让添加的标点能与单词一起渲染。适合语法/拼写差异输出。
* **智能转义字符清理**：将模型过度转义生成的字面量 `\n` 和 `\t` 转化为真正的换行和缩进（仅在安全的纯文本区域执行）。
* **LaTeX 现代化转换**：自动将旧式的 LaTeX 定界符（`\[...\]` 和 `\(...\)`）升级为现代 Markdown 标准（`$$...$$` 和 `$ ... $`）。
* **思维标签大一统**：无论模型输出的是 `<think>` 还是 `<thinking>`，统一标准化为 `<thought>` 标签。
* **残缺代码块修复**：修复乱码的语言前缀（例如 ` ```python`），调整缩进，并在模型回答被截断时，自动补充闭合的 ` ``` `。
* **列表与表格急救**：为粘连的编号列表注入换行，为残缺的 Markdown 表格补充末尾的闭合管道符（`|`）。
* **XML 伪影消除**：静默移除 Claude 模型经常泄露的 `<antArtifact>` 或 `<antThinking>` 残留标签。

### 3. 绝对的可靠性与安全 (100% Rollback)

- **无损回滚机制**：如果在修复过程中发生任何意外错误或崩溃，插件会立即捕获异常，并静默返回**绝对原始**的文本，确保你的对话永远不会因插件报错而丢失。

## 🌐 多语言支持 (i18n)

界面的状态提示气泡会根据你的浏览器语言自动切换：
`English`, `简体中文`, `繁體中文 (香港)`, `繁體中文 (台灣)`, `한국어`, `日本語`, `Français`, `Deutsch`, `Español`, `Italiano`, `Tiếng Việt`, `Bahasa Indonesia`

## 使用方法 🛠️

1. 在 Open WebUI 中安装此插件。
2. 全局启用或为特定模型启用此过滤器（强烈建议为格式输出不稳定的模型启用）。
3. 在 **Valves (配置参数)** 设置中微调你需要的修复项。

## 配置参数 (Valves) ⚙️

| 参数 | 默认值 | 描述 |
| :--- | :--- | :--- |
| `priority` | `50` | 过滤器优先级。数值越大越靠后（建议放在其他内容过滤器之后运行）。 |
| `enable_escape_fix` | `False` | 修复过度的转义字符（将字面量 `\n` 转换为实际换行）。**默认禁用以保证安全。** |
| `enable_escape_fix_in_code_blocks` | `False` | **高阶技巧**：如果你的 SQL 或 HTML 代码块总是挤在一行，**请开启此项**。如果你经常写 Python/C++，建议保持关闭。 |
| `enable_thought_tag_fix` | `True` | 规范化思维标签为 `<thought>`。 |
| `enable_details_tag_fix` | `True` | 修复 `<details>` 标签的排版间距。 |
| `enable_code_block_fix` | `True` | 修复代码块前缀、缩进和换行。 |
| `enable_latex_fix` | `True` | 规范化 LaTeX 定界符（`\[` -> `$$`）。 |
| `enable_list_fix` | `False` | 修复列表项换行（实验性）。 |
| `enable_unclosed_block_fix` | `True` | 自动闭合被截断的代码块。 |
| `enable_mermaid_fix` | `True` | 修复常见 Mermaid 语法错误（如自动加引号）。 |
| `enable_heading_fix` | `True` | 修复标题中缺失的空格 (`#Title` -> `# Title`)。 |
| `enable_table_fix` | `True` | 修复表格中缺失的闭合管道符。 |
| `enable_xml_tag_cleanup` | `True` | 清理残留的 XML 分析标签。 |
| `enable_emphasis_spacing_fix` | `False` | 修复强调语法（加粗/斜体）内部的多余空格。 |
| `enable_intra_word_emphasis_fix` | `False` | 将开头的强调标记移动到词的开头（如 `series**,**` → `**series,**`），让仅含标点的添加能正常渲染。适合语法/拼写差异输出。 |
| `show_status` | `True` | 当触发任何修复规则时，在页面底部显示提示气泡。 |
| `show_debug_log` | `False` | 在浏览器控制台 (F12) 打印修改前后的详细对比日志。 |

## ⭐ 支持

如果这个插件拯救了你的排版，欢迎到 [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions) 点个 Star，这是我持续改进的最大动力。感谢支持！

## 🧩 其他

* **故障排除**：遇到“负向修复”（即原本正常的排版被修坏了）？请开启 `show_debug_log`，在 F12 控制台复制出原始文本，并在 GitHub 提交 Issue：[提交 Issue](https://github.com/Fu-Jie/openwebui-extensions/issues)
