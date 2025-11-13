# Available Action Plugins

This directory contains various action plugins that can be used to extend Open WebUI functionality. Each plugin has its own documentation.

## Action Plugins List

| Plugin Name | Description | Version | Documentation |
| :--- | :--- | :--- | :--- |
| Smart Mind Map | Intelligently analyzes text content and generates interactive mind maps | 0.7.2 | [English](./思维导图/README.md) / [中文](./思维导图/README_CN.md) |

---

## What are Action Plugins?

Action plugins allow you to define custom functionalities that can be triggered from chat. Unlike filters, action plugins are typically used for:

-   Generating specific output formats (such as mind maps, charts, etc.)
-   Interacting with external APIs
-   Performing data transformations and processing
-   Saving or exporting content to files
-   Creating interactive visualizations

---

## How to Use Action Plugins

1. Download the plugin file (`.py`) to your local computer
2. In OpenWebUI Admin Settings, find the "Plugins" section
3. Select "Actions" type
4. Upload the downloaded file
5. After refreshing the page, select and enable the plugin in chat settings

---

## How to Contribute

We welcome community contributions of new action plugins!

1. **Fork** this repository
2. Create a new plugin directory under `plugins/actions/`
3. Add your plugin file (`.py`)
4. Create complete documentation in both Chinese and English (`README_CN.md` and `README.md`)
5. Update this README file to add your plugin to the list
6. Create a **Pull Request**

### Documentation Requirements

Each plugin should include:

-   **Core Features**: Main functionality and advantages of the plugin
-   **Installation and Configuration**: Detailed installation and configuration steps
-   **Configuration Parameters**: Description of all configurable parameters
-   **Usage**: Basic usage examples and best practices
-   **Troubleshooting**: Common issues and solutions

---

> **Developer Note**: When adding a new plugin, please ensure you also add the corresponding documentation and update this list.
