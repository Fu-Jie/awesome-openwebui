# Plugins（插件）

[English](./README.md) | 中文

此目录包含 OpenWebUI 的三种类型的插件：

- **Filters（过滤器）**: 在将用户输入发送给 LLM 前进行处理
- **Actions（动作）**: 从聊天中触发自定义功能
- **Pipes（管道）**: 在显示给用户前增强 LLM 响应

## 📦 插件类型概览

### 🔧 Filters（过滤器）(`/filters`)

过滤器在用户输入到达 LLM 前修改它。用途包括：

- 输入验证和规范化
- 添加系统提示或上下文
- 压缩长对话
- 预处理和格式化

[查看过滤器 →](./filters/README_CN.md)

### 🎬 Actions（动作）(`/actions`)

动作是从聊天中触发的自定义功能。用途包括：

- 生成输出（思维导图、图表等）
- 与外部 API 交互
- 数据转换
- 文件操作和导出
- 复杂工作流程

[查看动作 →](./actions/README_CN.md)

### 📤 Pipes（管道）(`/pipes`)

管道在 LLM 生成响应后处理它。用途包括：

- 响应格式化
- 内容增强
- 翻译和转换
- 响应过滤
- 与外部服务集成

[查看管道 →](./pipes/README_CN.md)

## 🚀 快速开始

### 安装插件

1. **下载**所需的插件文件（`.py`）
2. **打开** OpenWebUI 管理员设置 → 插件（Plugins）
3. **选择**插件类型（Filters、Actions 或 Pipes）
4. **上传**文件
5. **刷新**页面
6. **配置**聊天设置中的参数

### 使用插件

- **Filters（过滤器）**: 启用后自动应用于所有输入
- **Actions（动作）**: 在聊天时从动作菜单手动选择
- **Pipes（管道）**: 启用后自动应用于所有响应

## 📚 插件文档

每个插件目录包含：

- 插件代码（`.py` 文件）
- 英文文档（`README.md`）
- 中文文档（`README_CN.md`）
- 配置和使用指南

## 🛠️ 插件开发

要创建新插件：

1. 选择插件类型（Filter、Action 或 Pipe）
2. 导航到对应的目录
3. 为插件创建新文件夹
4. 编写清晰记录的插件代码
5. 创建 `README.md` 和 `README_CN.md`
6. 更新该目录中的主 README

### 插件结构模板

```python
plugins/
├── filters/
│   ├── my_filter/
│   │   ├── my_filter.py          # 插件代码
│   │   ├── my_filter_cn.py       # 可选：中文版本
│   │   ├── README.md              # 文档
│   │   └── README_CN.md           # 中文文档
│   └── README.md
├── actions/
│   ├── my_action/
│   │   ├── my_action.py
│   │   ├── README.md
│   │   └── README_CN.md
│   └── README.md
└── pipes/
    ├── my_pipe/
    │   ├── my_pipe.py
    │   ├── README.md
    │   └── README_CN.md
    └── README.md
```

## 📋 文档检查清单

每个插件应包含：

- [ ] 清晰的功能描述
- [ ] 配置参数及默认值
- [ ] 安装和设置说明
- [ ] 使用示例
- [ ] 故障排除指南
- [ ] 性能考虑
- [ ] 版本和作者信息

---

> **注意**：有关每种插件类型的详细信息，请参阅每个插件类型目录中的相应 README 文件。
