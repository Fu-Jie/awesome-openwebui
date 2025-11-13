# Filters

English | [中文](./README_CN.md)

Filters process and modify user input before it is sent to the LLM. This directory contains various filters that can be used to extend OpenWebUI functionality.

## 📋 Filter List

| Filter Name | Description | Documentation |
| :--- | :--- | :--- |
| **Async Context Compression** | Reduces token consumption in long conversations through intelligent summarization and message compression while maintaining conversational coherence. | [English](./async-context-compression/async_context_compression.md) / [中文](./async-context-compression/async_context_compression_cn.md) |

## 🚀 Quick Start

### Installing a Filter

1. Navigate to the desired filter directory
2. Download the corresponding `.py` file to your local machine
3. Open OpenWebUI Admin Settings and find the "Filters" section
4. Upload the Python file
5. Configure the filter parameters according to its documentation
6. Refresh the page and enable the filter in your chat settings

## 📖 Development Guide

When adding a new filter, please follow these steps:

1. **Create Filter Directory**: Create a new folder in the current directory (e.g., `my_filter/`)
2. **Write Filter Code**: Create a `.py` file with clear documentation of functionality and configuration in comments
3. **Write Documentation**:
   - Create `filter_name.md` (English version)
   - Create `filter_name_cn.md` (Chinese version)
   - Documentation should include: feature description, configuration parameters, usage examples, and troubleshooting
4. **Update This List**: Add your new filter to the table above

## ⚙️ Configuration Best Practices

- **Priority Management**: Set appropriate filter priority to ensure correct execution order
- **Parameter Tuning**: Adjust filter parameters based on your specific needs
- **Debug Logging**: Enable debug mode during development, disable in production
- **Performance Testing**: Test filter performance under high load

---

> **Contributor Note**: To ensure project maintainability and user experience, please provide clear and complete documentation for each new filter, including feature description, parameter configuration, usage examples, and troubleshooting guide.
