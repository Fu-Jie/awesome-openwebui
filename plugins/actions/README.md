# Actions (Action Plugins)

English | [中文](./README_CN.md)

Action plugins allow you to define custom functionalities that can be triggered from chat. This directory contains various action plugins that can be used to extend OpenWebUI functionality.

## 📋 Action Plugins List

| Plugin Name | Description | Version | Documentation |
| :--- | :--- | :--- | :--- |
| **Smart Mind Map** | Intelligently analyzes text content and generates interactive mind maps | 0.7.2 | [English](./smart-mind-map/README.md) / [中文](./smart-mind-map/README_CN.md) |

## 🎯 What are Action Plugins?

Action plugins typically used for:

- Generating specific output formats (such as mind maps, charts, tables, etc.)
- Interacting with external APIs or services
- Performing data transformations and processing
- Saving or exporting content to files
- Creating interactive visualizations
- Automating complex workflows

## 🚀 Quick Start

### Installing an Action Plugin

1. Download the plugin file (`.py`) to your local machine
2. Open OpenWebUI Admin Settings and find the "Plugins" section
3. Select the "Actions" type
4. Upload the downloaded file
5. Refresh the page and enable the plugin in chat settings
6. Use the plugin by selecting it from the available actions in chat

## 📖 Development Guide

When adding a new action plugin, please follow these steps:

1. **Create Plugin Directory**: Create a new folder under `plugins/actions/` (e.g., `my_action/`)
2. **Write Plugin Code**: Create a `.py` file with clear documentation of functionality
3. **Write Documentation**:
   - Create `README.md` (English version)
   - Create `README_CN.md` (Chinese version)
   - Include: feature description, configuration, usage examples, and troubleshooting
4. **Update This List**: Add your plugin to the table above

---

> **Contributor Note**: To ensure project quality, please provide clear and complete documentation for each new plugin, including features, configuration, usage examples, and troubleshooting guides.
