# Awesome OpenWebUI

[English](./README.md) | 中文

一个收集和分享 [OpenWebUI](https://github.com/open-webui/open-webui) 增强功能的项目。通过精选的提示词（Prompts）和插件（Plugins）来扩展 OpenWebUI 的功能，提升使用体验。

## 📦 项目内容

### 🎥 演示文稿 (Presentation)

- **从"问一个AI"到"运营一支AI团队"** - 深度解析 OpenWebUI 的协同能力与平台价值
  - 📄 [原始文章](./从问一个AI到运营一支AI团队.md) - 完整的 Markdown 文档
  - 🎬 [网页演示](./presentation.html) - 精美的网页版演示文稿（含流程图）
  - 📖 [使用指南](./PRESENTATION.md) - 演示文稿使用说明

### 🎯 提示词 (Prompts)

位于 `/prompts` 目录，包含针对不同领域的优质提示词模板：

- **编程类** (`/prompts/coding`): 代码生成、调试、优化相关的提示词
- **营销类** (`/prompts/marketing`): 内容创作、品牌策划、市场分析相关的提示词

每个提示词都独立保存为 Markdown 文件，可直接在 OpenWebUI 中使用。

### 🔧 插件 (Plugins)

位于 `/plugins` 目录，提供三种类型的插件扩展：

- **过滤器 (Filters)** - 在用户输入发送给 LLM 前进行处理和优化
  - 异步上下文压缩：智能压缩长上下文，优化 token 使用效率

- **动作 (Actions)** - 自定义功能，从聊天中触发
  - 思维导图生成：快速生成和导出思维导图

- **管道 (Pipes)** - 对 LLM 响应进行处理和增强
  - 各类响应处理和格式化插件

## 🚀 快速开始

### 使用提示词

1. 在 `/prompts` 目录中选择所需的提示词文件
2. 复制文件内容
3. 在 OpenWebUI 聊天界面中，点击"Prompt"按钮
4. 粘贴内容并保存

### 使用插件

1. 下载所需的插件文件（`.py`）到本地
2. 打开 OpenWebUI 管理员设置 (Admin Settings)
3. 在插件部分上传文件
4. 刷新页面，新插件即可在聊天设置中使用
