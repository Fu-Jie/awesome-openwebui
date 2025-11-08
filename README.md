# Awesome OpenWebUI

欢迎来到 Awesome OpenWebUI！这是一个旨在收集和分享高质量 [OpenWebUI](https://github.com/open-webui/open-webui) 增强功能的社区项目。

## 目标

本项目旨在为 OpenWebUI 用户提供一个中心化的平台，以发现、分享和使用各种提示词（Prompts）和插件（Plugins），从而增强用户体验、扩展功能。

## 目录结构

-   **/prompts**: 存放高质量、实用的提示词。每个提示词应该是一个独立的 Markdown 文件 (`.md`)。
    -   文件名应清晰地描述提示词的用途（例如 `technical_article_summarizer.md`）。
-   **/plugins**: 存放各类插件。
    -   **/filters**: Filter（过滤器）插件，通常在将用户的输入发送给 LLM 之前对其进行修改。
    -   **/actions**: Action（动作）插件，允许您定义可以从聊天中触发的自定义功能（例如，保存到文件、调用 API 等）。
    -   **/pipes**: Pipe（管道）插件，在 LLM 生成响应后、展示给用户之前，对响应内容进行处理和修改。

## 如何使用

### 提示词

1.  找到您感兴趣的提示词文件（例如 `prompts/technical_article_summarizer.md`）。
2.  复制文件内容。
3.  在 OpenWebUI 的聊天界面中，点击 "Prompt" 按钮，将内容粘贴进去并保存。

### 插件

1.  将相应的插件文件（`.py`）下载到您的本地计算机。
2.  在 OpenWebUI 的管理员设置（Admin Settings）中，找到插件（Plugins）部分。
3.  根据插件的类型（Filter, Action, Pipe），上传您下载的文件。
4.  刷新页面，新插件即可在聊天设置中选择和使用。

## 如何贡献

我们非常欢迎社区的贡献！

1.  **Fork** 本仓库。
2.  在相应的目录下添加您的提示词或插件。
    -   请确保您的文件名和内容清晰、规范。
    -   如果是插件，请添加适当的注释以解释其功能。
3.  创建一个 **Pull Request**。

感谢您的贡献！
