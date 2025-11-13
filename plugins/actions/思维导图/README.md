# Smart Mind Map - Mind Mapping Generation Plugin

**Author:** [Fu-Jie](https://github.com/Fu-Jie) | **Version:** 0.7.2 | **License:** MIT

> **Important**: To ensure the maintainability and usability of all plugins, each plugin should be accompanied by clear and comprehensive documentation to ensure its functionality, configuration, and usage are well explained.

Smart Mind Map is a powerful OpenWebUI action plugin that intelligently analyzes long-form text content and automatically generates interactive mind maps, helping users structure and visualize knowledge.

---

## Core Features

-   ✅ **Intelligent Text Analysis**: Automatically identifies core themes, key concepts, and hierarchical structures
-   ✅ **Interactive Visualization**: Generates beautiful interactive mind maps based on Markmap.js
-   ✅ **Multi-language Support**: Automatically adjusts output based on user language
-   ✅ **Real-time Rendering**: Renders mind maps directly in the chat interface without navigation
-   ✅ **Export Capabilities**: Supports copying SVG code and Markdown source
-   ✅ **Customizable Configuration**: Configurable LLM model, minimum text length, and other parameters

---

## How It Works

1. **Text Extraction**: Extracts text content from user messages (automatically filters HTML code blocks)
2. **Intelligent Analysis**: Analyzes text structure using the configured LLM model
3. **Markdown Generation**: Converts analysis results to Markmap-compatible Markdown format
4. **Visual Rendering**: Renders the mind map using Markmap.js in an HTML template
5. **Interactive Display**: Presents the mind map to users in an interactive format within the chat interface

---

## Installation and Configuration

### 1. Plugin Installation

1. Download the `思维导图.py` file to your local computer
2. In OpenWebUI Admin Settings, find the "Plugins" section
3. Select "Actions" type
4. Upload the downloaded file
5. Refresh the page, and the plugin will be available

### 2. Model Configuration

The plugin requires access to an LLM model for text analysis. Please ensure:

-   Your OpenWebUI instance has at least one available LLM model configured
-   Recommended to use fast, economical models (e.g., `gemini-2.5-flash`) for the best experience
-   Configure the `LLM_MODEL_ID` parameter in the plugin settings

### 3. Plugin Activation

Select the "Smart Mind Map" action plugin in chat settings to enable it.

---

## Configuration Parameters

You can adjust the following parameters in the plugin's settings (Valves):

| Parameter | Default | Description |
| :--- | :--- | :--- |
| `show_status` | `true` | Whether to display operation status updates in the chat interface (e.g., "Analyzing..."). |
| `LLM_MODEL_ID` | `gemini-2.5-flash` | LLM model ID for text analysis. Recommended to use fast and economical models. |
| `MIN_TEXT_LENGTH` | `100` | Minimum text length (in characters) required for mind map analysis. Text that's too short cannot generate valid mind maps. |

---

## Usage

### Basic Usage

1. Enable the "Smart Mind Map" action in chat settings
2. Input or paste long-form text content (at least 100 characters) in the conversation
3. After sending the message, the plugin will automatically analyze and generate a mind map
4. The mind map will be rendered directly in the chat interface

### Usage Example

**Input Text:**
```
Artificial Intelligence (AI) is a branch of computer science dedicated to creating systems capable of performing tasks that typically require human intelligence.
Main application areas include:
1. Machine Learning - Enables computers to learn from data
2. Natural Language Processing - Understanding and generating human language
3. Computer Vision - Recognizing and processing images
4. Robotics - Creating intelligent systems that can interact with the physical world
```

**Generated Result:**
The plugin will generate an interactive mind map centered on "Artificial Intelligence", including major application areas and their sub-concepts.

### Export Features

Generated mind maps support two export methods:

1. **Copy SVG Code**: Click the "Copy SVG Code" button to copy the mind map in SVG format to the clipboard
2. **Copy Markdown**: Click the "Copy Markdown" button to copy the raw Markdown format to the clipboard

---

## Technical Architecture

### Frontend Rendering

-   **Markmap.js**: Open-source mind mapping rendering engine
-   **D3.js**: Data visualization foundation library
-   **Responsive Design**: Adapts to different screen sizes

### Backend Processing

-   **LLM Integration**: Calls configured models via `generate_chat_completion`
-   **Text Preprocessing**: Automatically filters HTML code blocks, extracts plain text content
-   **Format Conversion**: Converts LLM output to Markmap-compatible Markdown format

### Security

-   **XSS Protection**: Automatically escapes `</script>` tags to prevent script injection
-   **Input Validation**: Checks text length to avoid invalid requests

---

## Troubleshooting

### Issue: Plugin Won't Start

**Solution:**
-   Check OpenWebUI logs for error messages
-   Confirm the plugin is correctly uploaded and enabled
-   Verify OpenWebUI version supports action plugins

### Issue: Text Content Too Short

**Symptom:** Prompt shows "Text content is too short for effective analysis"

**Solution:**
-   Ensure input text contains at least 100 characters (default configuration)
-   Lower the `MIN_TEXT_LENGTH` parameter value in plugin settings
-   Provide more detailed, structured text content

### Issue: Mind Map Not Generated

**Solution:**
-   Check if `LLM_MODEL_ID` is configured correctly
-   Confirm the configured model is available in OpenWebUI
-   Review backend logs for LLM call failures
-   Verify user has sufficient permissions to access the configured model

### Issue: Mind Map Display Error

**Symptom:** Shows "⚠️ Mind map rendering failed"

**Solution:**
-   Check browser console for error messages
-   Confirm Markmap.js and D3.js libraries are loading correctly
-   Verify generated Markdown format conforms to Markmap specifications
-   Try refreshing the page to re-render

### Issue: Export Function Not Working

**Solution:**
-   Confirm browser supports Clipboard API
-   Check if browser is blocking clipboard access permissions
-   Use modern browsers (Chrome, Firefox, Edge, etc.)

---

## Best Practices

1. **Text Preparation**
   -   Provide text content with clear structure and distinct hierarchies
   -   Use paragraphs, lists, and other formatting to help LLM understand text structure
   -   Avoid excessively lengthy or unstructured text

2. **Model Selection**
   -   For daily use, recommend fast models like `gemini-2.5-flash`
   -   For complex text analysis, use more powerful models (e.g., GPT-4)
   -   Balance speed and analysis quality based on needs

3. **Performance Optimization**
   -   Set `MIN_TEXT_LENGTH` appropriately to avoid processing text that's too short
   -   For particularly long texts, consider summarizing before generating mind maps
   -   Disable `show_status` in production environments to reduce interface updates

---

## Changelog

### v0.7.2 (Current Version)
-   Optimized text extraction logic, automatically filters HTML code blocks
-   Improved error handling and user feedback
-   Enhanced export functionality compatibility
-   Optimized UI styling and interactive experience

---

## License

This plugin is released under the MIT License.

## Contributing

Welcome to submit issue reports and improvement suggestions! Please visit the project repository: [awesome-openwebui](https://github.com/Fu-Jie/awesome-openwebui)

---

## Related Resources

-   [Markmap Official Website](https://markmap.js.org/)
-   [OpenWebUI Documentation](https://docs.openwebui.com/)
-   [D3.js Official Website](https://d3js.org/)
