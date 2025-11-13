# Pipes

English | [中文](./README_CN.md)

Pipes process and enhance LLM responses after they are generated and before they are displayed to the user. This directory contains various pipe plugins that can be used to extend OpenWebUI functionality.

## 📋 Pipe Plugins List

| Plugin Name | Description | Documentation |
| :--- | :--- | :--- |
| **Example Pipe** | A template/example for creating pipe plugins | [English](./example-pipe/README.md) / [中文](./example-pipe/README_CN.md) |
| **AI Agent Pipe** | Transforms AI responses into complete agent workflows with multiple thinking rounds and tool calls | [English](./ai-agent-pipe/README.md) / [中文](./ai-agent-pipe/README_CN.md) |

## 🎯 What are Pipe Plugins?

Pipe plugins process the output from the LLM and can:

- Format responses (convert to markdown, JSON, tables, etc.)
- Enhance responses with additional information
- Translate or transform content
- Filter or modify content before display
- Add watermarks or metadata
- Integrate with external services

Pipes are executed after the LLM generates a response but before the user sees it.

## 🚀 Quick Start

### Installing a Pipe Plugin

1. Download the plugin file (`.py`) to your local machine
2. Open OpenWebUI Admin Settings and find the "Plugins" section
3. Select the "Pipes" type
4. Upload the downloaded file
5. Refresh the page and enable the pipe in your chat settings
6. The pipe will be applied to all subsequent LLM responses

## 📖 Development Guide

When adding a new pipe plugin, please follow these steps:

1. **Create Plugin Directory**: Create a new folder under `plugins/pipes/` (e.g., `my_pipe/`)
2. **Write Plugin Code**: Create a `.py` file with clear documentation of functionality
3. **Write Documentation**:
   - Create `README.md` (English version)
   - Create `README_CN.md` (Chinese version)
   - Include: feature description, configuration, usage examples, and troubleshooting
4. **Update This List**: Add your plugin to the table above

## ⚙️ Best Practices for Pipe Development

- **Non-blocking Operations**: Keep pipe processing fast to avoid UI delays
- **Error Handling**: Gracefully handle errors without breaking the response
- **Configuration**: Make pipes configurable for different use cases
- **Performance**: Test with large responses to ensure efficiency
- **Documentation**: Provide clear examples and troubleshooting guides

---

> **Contributor Note**: We welcome contributions of new pipe plugins! Please provide clear and complete documentation for each new plugin, including features, configuration, usage examples, and troubleshooting guides.
