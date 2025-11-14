const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  const filePath = path.resolve('./presentation.html');
  if (!fs.existsSync(filePath)) {
    console.error(`Error: File not found at ${filePath}`);
    process.exit(1);
  }

  try {
    await page.goto(`file://${filePath}`, { waitUntil: 'networkidle' });

    // Wait for the first Mermaid diagram to be rendered
    await page.waitForSelector('.mermaid svg', { timeout: 15000 });
    console.log('Mermaid diagram SVG element found. Verification successful.');

    // Take screenshots of the first two slides for visual confirmation
    const slides = await page.$$('.marp-slide');
    if (slides.length > 0) {
      await slides[0].screenshot({ path: 'slide_1.png' });
      console.log('Screenshot of Slide 1 saved as slide_1.png');
    }
    if (slides.length > 1) {
      await slides[1].screenshot({ path: 'slide_2.png' });
      console.log('Screenshot of Slide 2 saved as slide_2.png');
    }

  } catch (error) {
    console.error('Verification failed:', error.message);
    await browser.close();
    process.exit(1);
  }

  await browser.close();
  console.log('Verification script finished successfully.');
})();
