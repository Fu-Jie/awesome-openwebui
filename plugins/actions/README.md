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

### Adding a New Action Plugin

When adding a new action plugin, please follow these steps:

1. **Create Plugin Directory**: Create a new folder under `plugins/actions/` (e.g., `my_action/`)
2. **Write Plugin Code**: Create a `.py` file with clear documentation of functionality
3. **Write Documentation**:
   - Create `README.md` (English version)
   - Create `README_CN.md` (Chinese version)
   - Include: feature description, configuration, usage examples, and troubleshooting
4. **Update This List**: Add your plugin to the table above

### Open WebUI Plugin Development Common Features

When developing Action plugins, you can use the following standard features provided by Open WebUI:

#### 1. **Plugin Metadata Definition**

```python
"""
title: Plugin Name
icon_url: data:image/svg+xml;base64,...  # Plugin icon (Base64 encoded SVG)
version: 1.0.0
description: Plugin functionality description
"""
```

#### 2. **Valves Configuration System**

Use Pydantic to define configurable parameters that users can adjust dynamically in the UI:

```python
from pydantic import BaseModel, Field

class Valves(BaseModel):
    show_status: bool = Field(
        default=True,
        description="Whether to show status updates"
    )
    api_key: str = Field(
        default="",
        description="API key"
    )
```

#### 3. **Standard Action Class Structure**

```python
class Action:
    def __init__(self):
        self.valves = self.Valves()
    
    async def action(
        self,
        body: dict,
        __user__: Optional[Dict[str, Any]] = None,
        __event_emitter__: Optional[Any] = None,
        __request__: Optional[Request] = None,
    ) -> Optional[dict]:
        # Plugin logic
        return body
```

#### 4. **Getting User Information**

```python
# Supports both dictionary and list formats
user_language = __user__.get("language", "en-US")
user_name = __user__.get("name", "User")
user_id = __user__.get("id", "unknown_user")
```

#### 5. **Event Emitter (event_emitter)**

**Sending notification messages:**

```python
await __event_emitter__({
    "type": "notification",
    "data": {
        "type": "info",      # info/warning/error/success
        "content": "Message content"
    }
})
```

**Sending status updates:**

```python
await __event_emitter__({
    "type": "status",
    "data": {
        "description": "Status description",
        "done": False,       # True when completed
        "hidden": False      # True to hide
    }
})
```

#### 6. **Calling Built-in LLM**

```python
from open_webui.utils.chat import generate_chat_completion
from open_webui.models.users import Users

# Get user object
user_obj = Users.get_user_by_id(user_id)

# Build LLM request
llm_payload = {
    "model": "model-id",
    "messages": [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "User input"}
    ],
    "temperature": 0.7,
    "stream": False
}

# Call LLM
llm_response = await generate_chat_completion(
    __request__, llm_payload, user_obj
)
```

#### 7. **Handling Message Body**

```python
# Read messages
messages = body.get("messages")
user_message = messages[-1]["content"]

# Modify messages
body["messages"][-1]["content"] = f"{user_message}\n\nAdditional content"

# Return modified body
return body
```

#### 8. **Embedding HTML Content**

```python
html_content = "<div>Interactive content</div>"
html_embed_tag = f"```html\n{html_content}\n```"
body["messages"][-1]["content"] = f"{text}\n\n{html_embed_tag}"
```

#### 9. **Async Processing**

All plugin methods must be asynchronous:

```python
async def action(...):
    await __event_emitter__(...)
    result = await some_async_function()
    return result
```

#### 10. **Error Handling and Logging**

```python
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

try:
    # Plugin logic
    pass
except Exception as e:
    logger.error(f"Error: {str(e)}", exc_info=True)
    await __event_emitter__({
        "type": "notification",
        "data": {"type": "error", "content": f"Operation failed: {str(e)}"}
    })
```

### Development Best Practices

1. **Use Valves Configuration**: Allow users to customize plugin behavior
2. **Provide Real-time Feedback**: Use event emitter to inform users of progress
3. **Graceful Error Handling**: Catch exceptions and provide friendly messages
4. **Support Multiple Languages**: Get language preference from `__user__`
5. **Logging**: Record key operations and errors for debugging
6. **Validate Input**: Check required parameters and data formats
7. **Return Complete Body**: Ensure message flow is properly passed

---

> **Contributor Note**: To ensure project quality, please provide clear and complete documentation for each new plugin, including features, configuration, usage examples, and troubleshooting guides. Refer to the common features above when developing your plugins.
