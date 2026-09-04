# 闪记卡 (Flash Card)

快速将文本提炼为精美的学习记忆卡片，自动抽取标题、摘要、关键要点、标签和分类，适合复习与分享。

| 作者：[Fu-Jie](https://github.com/Fu-Jie) · v0.2.6 | [⭐ 点个 Star 支持项目](https://github.com/Fu-Jie/openwebui-extensions) |
| :--- | ---: |

| ![followers](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_followers.json&label=%F0%9F%91%A5&style=flat) | ![points](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_points.json&label=%E2%AD%90&style=flat) | ![top](https://img.shields.io/badge/%F0%9F%8F%86-Top%20%3C1%25-10b981?style=flat) | ![contributions](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_contributions.json&label=%F0%9F%93%A6&style=flat) | ![downloads](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_downloads.json&label=%E2%AC%87%EF%B8%8F&style=flat) | ![saves](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_saves.json&label=%F0%9F%92%BE&style=flat) | ![views](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2FFu-Jie%2Fdb3d95687075a880af6f1fba76d679c6%2Fraw%2Fbadge_views.json&label=%F0%9F%91%81%EF%B8%8F&style=flat) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |

## 使用 Batch Install Plugins 安装

如果你已经安装了 [Batch Install Plugins from GitHub](https://openwebui.com/posts/batch_install_plugins_install_popular_plugins_in_s_c9fd6e80) ，可以用下面这句来安装或更新当前插件：

```text
从 Fu-Jie/openwebui-extensions 安装插件
```

当选择弹窗打开后，搜索当前插件，勾选后继续安装即可。

> [!IMPORTANT]
> 如果你已经安装了 OpenWebUI 官方社区里的同名版本，请先删除旧版本，否则重新安装时可能报错。删除后，Batch Install Plugins 后续就可以继续负责更新这个插件。

## v0.2.6 最新更新

- **OpenWebUI 0.11+ Rich UI 兼容性**：成功生成后现在返回内联 `HTMLResponse`，OpenWebUI 可以将生成的卡片作为 Rich UI embed 推送并显示。
- **可靠渲染**：移除了新版 OpenWebUI 不再持久化或渲染的 fenced HTML 消息修改方式。

## 核心特性 🔑

* **一键生成**：输入任意文本，直接产出结构化卡片。
* **要点聚合**：自动提取 3-5 个记忆要点与 2-4 个标签。
* **多语言支持**：可设定目标语言（默认中文）。
* **渐进合并**：多次调用会将新卡片合并到同一 HTML 容器中；如需重置可启用清空选项。
* **状态提示**：实时推送“生成中/完成/错误”等状态与通知。

## 使用方法 🛠️

1. **安装**: 在插件市场安装并启用“闪记卡”。
2. **配置**: 根据需要调整 Valves 设置（可选）。
3. **触发**: 将待整理的文本发送到聊天框。
4. **结果**: 等待状态提示，生成的卡片会以内联 Rich UI embed 的形式渲染。

## 配置参数 (Valves) ⚙️

| 参数                | 说明                                  | 默认值 |
| ------------------- | ------------------------------------- | ------ |
| MODEL_ID            | 指定推理模型；为空则使用当前会话模型  | 空     |
| MIN_TEXT_LENGTH     | 最小文本长度，不足时提示补充          | 50     |
| LANGUAGE            | 输出语言（如 zh、en）                 | zh     |
| SHOW_STATUS         | 是否显示状态更新                      | true   |
| CLEAR_PREVIOUS_HTML | 是否清空旧的卡片 HTML（否则合并追加） | false  |
| MESSAGE_COUNT       | 取最近 N 条消息生成卡片               | 1      |

## ⭐ 支持

如果这个插件对你有帮助，欢迎到 [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions) 点个 Star，这将是我持续改进的动力，感谢支持。

## 故障排除 (Troubleshooting) ❓

* **插件不工作？**: 请检查是否在模型设置中启用了该过滤器/动作。
* **调试日志**: 在 Valves 中启用 `SHOW_STATUS` 以查看进度更新。
* **错误信息**: 如果看到错误，请复制完整的错误信息并报告。
* **提交 Issue**: 如果遇到任何问题，请在 GitHub 上提交 Issue：[OpenWebUI Extensions Issues](https://github.com/Fu-Jie/openwebui-extensions/issues)

## 预览 📸

![闪记卡示例](https://raw.githubusercontent.com/Fu-Jie/openwebui-extensions/main/plugins/actions/flash-card/flash_card_cn.png)

## 更新日志

完整历史请查看 GitHub 项目： [OpenWebUI Extensions](https://github.com/Fu-Jie/openwebui-extensions)
