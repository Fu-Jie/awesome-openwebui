# Filter Plugins

Filter plugins process and modify messages before they are sent to the LLM or after responses are generated.

## What are Filters?

Filters act as middleware in the message pipeline:

- :material-arrow-right-bold: **Inlet**: Process user messages before they reach the LLM
- :material-arrow-left-bold: **Outlet**: Process LLM responses before they're displayed
- :material-stream: **Stream**: Process streaming responses in real-time

---

## Available Filter Plugins

<div class="grid cards" markdown>

- :material-arrow-collapse-vertical:{ .lg .middle } **Async Context Compression**

    ---

    Reduces token consumption in long conversations with safer summary fallbacks and clearer failure visibility.

    **Version:** 1.6.3

    [:octicons-arrow-right-24: Documentation](async-context-compression.md)

- :material-text-box-plus:{ .lg .middle } **Context Enhancement**

    ---

    Enhances chat context with additional information for better responses.

    **Version:** 0.2

    [:octicons-arrow-right-24: Documentation](context-enhancement.md)

- :material-folder-refresh:{ .lg .middle } **Folder Memory**

    ---

    Automatically extracts consistent "Project Rules" from ongoing conversations within a folder and injects them back into the folder's system prompt.

    **Version:** 0.1.0

    [:octicons-arrow-right-24: Documentation](folder-memory.md)

- :material-format-paint:{ .lg .middle } **Markdown Normalizer**

    ---

    Fixes common Markdown formatting issues in LLM outputs, including Mermaid syntax, code blocks, and LaTeX formulas.

    **Version:** 1.2.8

    [:octicons-arrow-right-24: Documentation](markdown_normalizer.md)

- :material-merge:{ .lg .middle } **Multi-Model Context Merger**

    ---

    Automatically merges context from multiple model responses in the previous turn, enabling collaborative answers.

    **Version:** 0.1.0

    [:octicons-arrow-right-24: Documentation](multi-model-context-merger.md)

- :material-file-document-multiple:{ .lg .middle } **Web Gemini Multimodal Filter**

    ---

    A powerful filter that provides multimodal capabilities (PDF, Office, Images, Audio, Video) to any model in OpenWebUI.

    **Version:** 0.3.2

    [:octicons-arrow-right-24: Documentation](web-gemini-multimodel.md)

- :material-file-shield:{ .lg .middle } **Copilot SDK Files Filter**

    ---

    A specialized filter to bypass OpenWebUI's default RAG for GitHub Copilot SDK models. It ensures the Agent receives raw files for autonomous analysis.

    **Version:** 0.1.3

    [:octicons-arrow-right-24: Documentation](github-copilot-sdk-files-filter.md)

</div>

---

## How Filters Work

```mermaid
graph LR
    A[User Message] --> B[Inlet Filter]
    B --> C[LLM]
    C --> D[Outlet Filter]
    D --> E[Display to User]
```

### Inlet Processing

The `inlet` method processes messages before they reach the LLM:

```python
async def inlet(self, body: dict, __metadata__: dict) -> dict:
    # Modify the request before sending to LLM
    messages = body.get("messages", [])
    # Add context, modify prompts, etc.
    return body
```

### Outlet Processing

The `outlet` method processes responses after they're generated:

```python
async def outlet(self, body: dict, __metadata__: dict) -> dict:
    # Modify the response before displaying
    messages = body.get("messages", [])
    # Format output, add citations, etc.
    return body
```

---

## Quick Installation

1. Download the desired filter `.py` file
2. Navigate to **Admin Panel** → **Settings** → **Functions**
3. Upload the file and configure settings
4. Enable the filter in chat settings or globally

---

## Development Template

```python
"""
title: My Custom Filter
author: Your Name
version: 1.0.0
description: Description of your filter plugin
"""

from pydantic import BaseModel, Field
from typing import Optional

class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=0,
            description="Filter priority (lower = earlier execution)"
        )
        enabled: bool = Field(
            default=True,
            description="Enable/disable this filter"
        )
    
    def __init__(self):
        self.valves = self.Valves()
    
    async def inlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __metadata__: Optional[dict] = None
    ) -> dict:
        """Process messages before sending to LLM."""
        if not self.valves.enabled:
            return body
        
        # Your inlet logic here
        messages = body.get("messages", [])
        
        return body
    
    async def outlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __metadata__: Optional[dict] = None
    ) -> dict:
        """Process responses before displaying."""
        if not self.valves.enabled:
            return body
        
        # Your outlet logic here
        
        return body
```

For more details, check our [Plugin Development Guide](../../development/plugin-guide.md).
