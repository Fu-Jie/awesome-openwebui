# Presentation Deployment Guide

This guide provides instructions on how to view the presentation generated from `从问一个AI到运营一支AI团队.md`.

There are two methods to view the presentation. The **recommended method** ensures the highest quality and full functionality, including interactive diagrams.

---

## Method 1: Recommended (Using VS Code + Marp Extension)

This method uses the original Markdown source file (`presentation.md`) and provides the best viewing experience.

### Prerequisites

1.  **Visual Studio Code**: Ensure you have VS Code installed. You can download it from [code.visualstudio.com](https://code.visualstudio.com/).
2.  **Marp for VS Code Extension**: This is a free extension that turns VS Code into a powerful presentation tool.

### Steps

1.  **Install the Extension**:
    *   Open Visual Studio Code.
    *   Go to the Extensions view by clicking on the Extensions icon in the Activity Bar on the side of the window or by pressing `Ctrl+Shift+X`.
    *   Search for `Marp for VS Code`.
    *   Click **Install**.

2.  **Open the Presentation File**:
    *   Open the `presentation.md` file in VS Code.

3.  **View the Presentation**:
    *   Click the **"Open Preview"** icon in the top-right corner of the editor.
    *   A live preview of the slide deck will appear. You can navigate through the slides, and all Mermaid diagrams will be fully rendered and interactive.

4.  **Exporting (Optional)**:
    *   With the preview open, you can export the presentation to HTML or PDF. Click the **Marp icon** in the top-right corner of the preview pane and select your desired export format.

---

## Method 2: Alternate (Using the HTML File)

This method uses the pre-compiled `presentation.html` file. It's a quick way to view the content, but it may have rendering issues with the diagrams.

### Steps

1.  **Open in a Web Browser**:
    *   Locate the `presentation.html` file in your file explorer.
    *   Right-click on it and choose "Open with" your favorite web browser (e.g., Chrome, Firefox, Edge).

### Important Note

Due to inconsistencies with JavaScript library execution in different environments, the **Mermaid diagrams within `presentation.html` may not render correctly**. If you see text descriptions of graphs instead of the actual diagrams, please use the **Recommended Method** above for a guaranteed viewing experience.
