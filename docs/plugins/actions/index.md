# Action Plugins

Action plugins add custom buttons below messages in the chat interface, allowing you to trigger specific functionalities with a single click.

## What are Actions?

Actions are interactive plugins that:

- :material-gesture-tap: Add buttons to the message action bar
- :material-export: Generate and export content (mind maps, charts, files)
- :material-api: Interact with external services and APIs
- :material-animation-play: Create visualizations and interactive content

---

## Available Action Plugins

<div class="grid cards" markdown>

- :material-brain:{ .lg .middle } **Smart Mind Map**

    ---

    Intelligently analyzes text content and generates interactive mind maps with beautiful visualizations.

    **Version:** 1.0.0

    [:octicons-arrow-right-24: Documentation](smart-mind-map.md)

- :material-chart-bar:{ .lg .middle } **Smart Infographic**

    ---

    Transform text into professional infographics using AntV visualization engine with various templates.

    **Version:** 1.6.0

    [:octicons-arrow-right-24: Documentation](smart-infographic.md)

- :material-card-text:{ .lg .middle } **Flash Card**

    ---

    Quickly generates beautiful flashcards from text, extracting key points and categories.

    **Version:** 0.2.4

    [:octicons-arrow-right-24: Documentation](flash-card.md)

- :material-file-excel:{ .lg .middle } **Export to Excel**

    ---

    Export chat conversations to Excel spreadsheet format for analysis and archiving.

    **Version:** 0.3.7

    [:octicons-arrow-right-24: Documentation](export-to-excel.md)

- :material-file-word-box:{ .lg .middle } **Export to Word (Enhanced Formatting)**

    ---

    Export the current conversation to a formatted Word doc with **syntax highlighting**, **native math equations**, **Mermaid diagrams**, **citations**, and **enhanced table formatting**.

    **Version:** 0.4.4

    [:octicons-arrow-right-24: Documentation](export-to-word.md)

- :material-brain:{ .lg .middle } **Deep Dive**

    ---

    A comprehensive thinking lens that dives deep into any content - Context → Logic → Insight → Path. Supports theme auto-adaptation.

    **Version:** 1.0.0

    [:octicons-arrow-right-24: Documentation](deep-dive.md)

</div>

---

## Quick Installation

1. Download the desired plugin `.py` file
2. Navigate to **Admin Panel** → **Settings** → **Functions**
3. Upload the file and configure settings
4. Use the action button in chat messages

---

## Development Template

Want to create your own Action plugin? Use our template:

```python
"""
title: My Custom Action
author: Your Name
version: 1.0.0
description: Description of your action plugin
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class Action:
    class Valves(BaseModel):
        # Add your configuration options here
        show_status: bool = Field(
            default=True,
            description="Show status updates during processing"
        )
    
    def __init__(self):
        self.valves = self.Valves()
    
    async def action(
        self,
        body: dict,
        __user__: Optional[Dict[str, Any]] = None,
        __event_emitter__: Optional[Any] = None,
        __request__: Optional[Any] = None,
    ) -> Optional[dict]:
        """
        Main action method triggered when user clicks the action button.
        
        Args:
            body: Message body containing conversation data
            __user__: Current user information
            __event_emitter__: For sending notifications and status updates
            __request__: FastAPI request object
        
        Returns:
            Modified body dict or None
        """
        # Send status update
        if __event_emitter__ and self.valves.show_status:
            await __event_emitter__({
                "type": "status",
                "data": {"description": "Processing...", "done": False}
            })
        
        # Your plugin logic here
        messages = body.get("messages", [])
        if messages:
            last_message = messages[-1].get("content", "")
            # Process the message...
        
        # Complete status
        if __event_emitter__ and self.valves.show_status:
            await __event_emitter__({
                "type": "status",
                "data": {"description": "Done!", "done": True}
            })
        
        return body
```

For more details, check our [Plugin Development Guide](../../development/plugin-guide.md).
