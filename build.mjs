import fs from 'fs/promises';
import { marked } from 'marked';
// FIX: Import the core module for Node.js environment
import mermaid from 'mermaid/dist/mermaid.core.mjs';
import { JSDOM } from 'jsdom';

const HTML_TEMPLATE = `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>从问一个AI到运营一支AI团队</title>
<style>
/* Basic Marp styles */
:root {
  --marp-theme-color-background: #fff;
  --marp-theme-color-highlight: #4fc3f7;
  --marp-theme-color-text: #000;
  --marp-theme-color-dimmed: #888;
  --marp-theme-font-family: 'Segoe UI', 'Helvetica Neue', sans-serif;
  --marp-theme-font-family-heading: 'Segoe UI', 'Helvetica Neue', sans-serif;
  --marp-theme-font-size: 30px;
  --marp-theme-line-height: 1.5;
  --marp-theme-header-color: #005588;
  --marp-theme-paginate-color: #ccc;
  --marp-theme-paginate-font-size: 15px;
}
body { margin: 0; font-family: var(--marp-theme-font-family); font-size: var(--marp-theme-font-size); line-height: var(--marp-theme-line-height); background: var(--marp-theme-color-background); color: var(--marp-theme-color-text); }
.marp-slide { box-sizing: border-box; width: 1280px; height: 720px; padding: 40px; display: flex; flex-direction: column; align-items: stretch; justify-content: flex-start; position: relative; overflow: hidden; border: 1px solid #ddd; margin: 20px auto; }
.marp-slide h1, .marp-slide h2 { font-family: var(--marp-theme-font-family-heading); color: var(--marp-theme-header-color); }
.marp-paginate { position: absolute; bottom: 20px; right: 20px; font-size: var(--marp-theme-paginate-font-size); color: var(--marp-theme-paginate-color); }
.mermaid { text-align: center; }
</style>
</head>
<body>
<div id="presentation-container">
__CONTENT__
</div>
</body>
</html>`;

async function renderMermaid(code, id) {
  const dom = new JSDOM('<!DOCTYPE html><body><div id="container"></div></body>');
  const { window } = dom;
  const container = window.document.getElementById('container');

  // The mermaid.core.mjs module exports a default object with the API
  const mermaidAPI = mermaid.default;
  mermaidAPI.initialize({ startOnLoad: false, theme: 'default', securityLevel: 'loose' });
  const { svg } = await mermaidAPI.render(id, code, container);
  return svg;
}

async function buildPresentation() {
    console.log('Starting presentation build...');
    try {
        const markdownContent = await fs.readFile('presentation.md', 'utf-8');
        const slidesMd = markdownContent.split('---').slice(2).map(s => s.trim());

        let finalHtmlContent = '';
        let slideNumber = 1;

        for (const slideMd of slidesMd) {
            if (!slideMd) continue;

            let processedMd = slideMd;
            const mermaidBlocks = [];

            processedMd = processedMd.replace(/```mermaid([\s\S]*?)```/g, (match, code) => {
                const placeholderId = `mermaid-placeholder-${mermaidBlocks.length}`;
                mermaidBlocks.push({ id: `mermaid-graph-${slideNumber}-${mermaidBlocks.length}`, code: code.trim() });
                return `<div id="${placeholderId}"></div>`;
            });

            let slideHtml = marked.parse(processedMd);

            for (let i = 0; i < mermaidBlocks.length; i++) {
                const block = mermaidBlocks[i];
                const svg = await renderMermaid(block.code, block.id);
                const placeholderId = `mermaid-placeholder-${i}`;
                slideHtml = slideHtml.replace(`<div id="${placeholderId}"></div>`, `<div class="mermaid">${svg}</div>`);
            }

            const paginateHtml = `<div class="marp-paginate">${slideNumber++}</div>`;
            finalHtmlContent += `<div class="marp-slide">${slideHtml}${paginateHtml}</div>\n`;
        }

        const finalHtml = HTML_TEMPLATE.replace('__CONTENT__', finalHtmlContent);
        await fs.writeFile('presentation.html', finalHtml);
        console.log('Presentation build successful! Output to presentation.html');

    } catch (error) {
        console.error('Error building presentation:', error);
        process.exit(1);
    }
}

buildPresentation();
