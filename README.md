# Awesome OpenWebUI

English | [中文](./README_CN.md)

A curated collection of enhancements for [OpenWebUI](https://github.com/open-webui/open-webui). Extend OpenWebUI's functionality with high-quality prompts and plugins to enhance your experience.

## 📦 Project Contents

### 🎯 Prompts

Located in the `/prompts` directory, containing curated prompt templates for various domains:

- **Coding** (`/prompts/coding`): Prompts for code generation, debugging, and optimization
- **Marketing** (`/prompts/marketing`): Prompts for content creation, branding, and market analysis

Each prompt is stored as an independent Markdown file and can be used directly in OpenWebUI.

### 🔧 Plugins

Located in the `/plugins` directory, offering three types of plugin extensions:

- **Filters** - Process and optimize user input before sending to LLM
  - Async Context Compression: Intelligently compress long contexts to optimize token usage

- **Actions** - Custom functionality that can be triggered from chat
  - Mind Map Generation: Quickly generate and export mind maps

- **Pipes** - Process and enhance LLM responses
  - Various response processing and formatting plugins

## 🚀 Quick Start

### Using Prompts

1. Select the desired prompt file from the `/prompts` directory
2. Copy the file content
3. In OpenWebUI chat interface, click the "Prompt" button
4. Paste the content and save

### Using Plugins

1. Download the desired plugin file (`.py`) to your local machine
2. Open OpenWebUI Admin Settings
3. Upload the file in the Plugins section
4. Refresh the page and the new plugin will be available in chat settings
