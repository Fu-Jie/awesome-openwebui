# OpenWebUI 演示文稿使用指南

## 📖 简介

这是一个基于文章《从"问一个AI"到"运营一支AI团队"》生成的网页版演示文稿，使用 Reveal.js 和 Mermaid.js 实现了精美的幻灯片展示和流程图渲染。

## 🚀 快速开始

### 方法一：直接在浏览器中打开

1. 在项目根目录找到 `presentation.html` 文件
2. 双击文件，或右键选择"使用浏览器打开"
3. 推荐使用现代浏览器（Chrome、Firefox、Safari、Edge）

### 方法二：通过 HTTP 服务器访问（推荐）

使用本地服务器可以获得更好的体验：

```bash
# Python 3
cd /path/to/awesome-openwebui
python3 -m http.server 8080

# Python 2
python -m SimpleHTTPServer 8080

# Node.js (需要安装 http-server)
npx http-server -p 8080
```

然后在浏览器中访问：http://localhost:8080/presentation.html

### 方法三：使用 VS Code Live Server

1. 安装 VS Code 扩展：Live Server
2. 右键点击 `presentation.html`
3. 选择 "Open with Live Server"

## 🎮 操作指南

### 基本导航

- **下一页**：方向键 → 或 ↓，空格键，或点击右侧控制按钮
- **上一页**：方向键 ← 或 ↑，或点击左侧控制按钮
- **回到首页**：Home 键
- **跳到末页**：End 键
- **全屏概览**：按 ESC 或 O 键
- **全屏演示**：按 F 键

### 高级功能

- **缩放**：按住 Alt/Option 键并点击任意位置
- **幻灯片编号**：自动显示在右下角
- **进度条**：显示在底部
- **键盘帮助**：按 ? 键查看完整快捷键列表

## 🎨 特色功能

### ✨ 完美渲染的 Mermaid 流程图

- 所有流程图使用 Mermaid.js 实时渲染
- 暗色主题，配色与演示文稿风格统一
- 流程图会在切换到对应幻灯片时自动渲染
- 支持所有 Mermaid 图表类型（流程图、序列图、甘特图等）

### 🎯 响应式设计

- 自适应各种屏幕尺寸
- 支持触摸屏操作（滑动切换幻灯片）
- 移动设备友好

### 🌈 精美样式

- 深色主题，护眼舒适
- 渐变色彩，视觉效果出众
- 自定义字体和排版
- 代码高亮显示

## 📋 内容结构

演示文稿分为三大部分：

1. **第一部分：构建AI团队的基础 - 多模型协同对话系统**
   - 多模型独立并行
   - @提及特定模型
   - 智能合并总结
   - 内容选中与深度追问

2. **第二部分：超越聊天的智能工作台 - 组织、知识与自动化**
   - 文件夹管理
   - 知识库系统
   - 用户提示词
   - 自定义模型配置

3. **第三部分：扩展功能 - Functions、Tools、OpenAPI Server 和 MCP Server**
   - Functions（函数）
   - Tools（工具）
   - OpenAPI Server
   - MCP Server

## 🔧 技术栈

- **Reveal.js 4.5.0** - 专业的 HTML 演示框架
- **Mermaid.js 10** - 流程图和图表渲染
- **现代 CSS3** - 精美样式和动画
- **响应式设计** - 适配各种设备

## 📝 自定义修改

如果你想自定义演示文稿，可以编辑 `presentation.html` 文件：

### 修改主题颜色

在 `<style>` 标签中找到 CSS 变量：

```css
:root {
    --r-background-color: #0a0e27;  /* 背景色 */
    --r-heading-color: #42b883;      /* 标题色 */
    --r-link-color: #42b883;         /* 链接色 */
}
```

### 修改内容

找到 JavaScript 中的 `markdownContent` 变量，直接编辑 Markdown 内容。

### 添加新幻灯片

在 Markdown 内容中使用 `---` 分隔不同的幻灯片。

## 🐛 故障排查

### 流程图不显示

1. 确保使用 HTTP 服务器访问（而不是直接打开文件）
2. 检查浏览器控制台是否有错误
3. 尝试刷新页面（Ctrl/Cmd + R）

### 中文显示异常

确保浏览器编码设置为 UTF-8。

### 样式显示不正常

1. 检查网络连接（需要加载 CDN 资源）
2. 清除浏览器缓存
3. 尝试使用其他浏览器

## 📤 分享演示文稿

### 本地分享

将 `presentation.html` 文件发送给他人，他们可以直接在浏览器中打开。

### 在线部署

可以将文件部署到以下平台：

- **GitHub Pages**：免费，简单
- **Netlify**：一键部署
- **Vercel**：现代化部署
- **GitLab Pages**：CI/CD 集成

## 🌟 最佳实践

1. **演示前检查**：提前打开并浏览所有幻灯片
2. **全屏模式**：按 F 键进入全屏获得最佳体验
3. **概览模式**：按 ESC 查看所有幻灯片布局
4. **缩放功能**：遇到需要强调的内容可以使用 Alt+点击 进行放大
5. **备份方案**：准备 PDF 版本以防技术问题

## 📚 相关资源

- [Reveal.js 官方文档](https://revealjs.com/)
- [Mermaid.js 官方文档](https://mermaid.js.org/)
- [OpenWebUI GitHub](https://github.com/open-webui/open-webui)
- [OpenWebUI 官方文档](https://docs.openwebui.com/)

## 📄 许可证

本演示文稿基于原文《从"问一个AI"到"运营一支AI团队"》创建，遵循项目的开源许可证。

---

**提示**：如有任何问题或建议，欢迎在 GitHub 仓库中提出 Issue！
