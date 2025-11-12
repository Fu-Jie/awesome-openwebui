# Async Context Compression Filter

**Author:** [Fu-Jie](https://github.com/Fu-Jie) | **Version:** 1.0.0 | **License:** MIT

> **Important Note**: To ensure the maintainability and usability of all filters, each filter should be accompanied by clear and complete documentation to fully explain its functionality, configuration, and usage.

This filter significantly reduces token consumption in long conversations by using intelligent summarization and message compression, while maintaining conversational coherence.

---

## Core Features

-   ✅ **Automatic Compression**: Triggers context compression automatically based on a message count threshold.
-   ✅ **Asynchronous Summarization**: Generates summaries in the background without blocking the current chat response.
-   ✅ **Persistent Storage**: Supports both PostgreSQL and SQLite databases to ensure summaries are not lost after a service restart.
-   ✅ **Flexible Retention Policy**: Freely configure the number of initial and final messages to keep, ensuring critical information and context continuity.
-   ✅ **Smart Injection**: Intelligently injects the generated historical summary into the new context.

---

## Installation & Configuration

### 1. Environment Variable

This plugin requires a database connection. You **must** configure the `DATABASE_URL` in your Open WebUI environment variables.

-   **PostgreSQL Example**:
    ```
    DATABASE_URL=postgresql://user:password@host:5432/openwebui
    ```
-   **SQLite Example**:
    ```
    DATABASE_URL=sqlite:///path/to/your/data/webui.db
    ```

### 2. Filter Order

It is recommended to set the priority of this filter relatively high (a smaller number) to ensure it runs before other filters that might modify message content. A typical order might be:

1.  **Pre-Filters (priority < 10)**
    -   e.g., A filter that injects a system-level prompt.
2.  **This Compression Filter (priority = 10)**
3.  **Post-Filters (priority > 10)**
    -   e.g., A filter that formats the final output.

---

## Configuration Parameters

You can adjust the following parameters in the filter's settings:

| Parameter | Default | Description |
| :--- | :--- | :--- |
| `priority` | `10` | The execution order of the filter. Lower numbers run first. |
| `compression_threshold` | `15` | When the total message count reaches this value, a background summary generation will be triggered. |
| `keep_first` | `1` | Always keep the first N messages. The first message often contains important system prompts. |
| `keep_last` | `6` | Always keep the last N messages to ensure contextual coherence. |
| `summary_model` | `None` | The model used for generating summaries. **Strongly recommended** to set a fast, economical, and compatible model (e.g., `gemini-2.5-flash`). If left empty, it will try to use the current chat's model, which may fail if it's an incompatible model type (like a Pipe model). |
| `max_summary_tokens` | `4000` | The maximum number of tokens allowed for the generated summary. |
| `summary_temperature` | `0.3` | Controls the randomness of the summary. Lower values are more deterministic. |
| `debug_mode` | `true` | Whether to print detailed debug information to the log. Recommended to set to `false` in production. |

---

## Troubleshooting

-   **Problem: Database connection failed.**
    -   **Solution**: Please ensure the `DATABASE_URL` environment variable is set correctly and that the database service is running.

-   **Problem: Summary not generated.**
    -   **Solution**: Check if the `compression_threshold` has been met and verify that `summary_model` is configured correctly. Check the logs for detailed errors.

-   **Problem: Initial system prompt is lost.**
    -   **Solution**: Ensure `keep_first` is set to a value greater than 0 to preserve the initial messages containing important information.

-   **Problem: Compression effect is not significant.**
    -   **Solution**: Try increasing the `compression_threshold` or decreasing the `keep_first` / `keep_last` values.
