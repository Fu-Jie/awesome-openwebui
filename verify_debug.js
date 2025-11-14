const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  // Listen for any errors that happen inside the page
  page.on('pageerror', error => {
    console.error('Error in page:', error);
  });

  const filePath = path.resolve('./presentation.html');
  if (!fs.existsSync(filePath)) {
    console.error(`Error: File not found at ${filePath}`);
    process.exit(1);
  }

  try {
    await page.goto(`file://${filePath}`, { waitUntil: 'networkidle' });

    // Give it a generous amount of time to render everything
    await new Promise(resolve => setTimeout(resolve, 5000));

    // Log the entire body's HTML to see what's going on
    const bodyHtml = await page.evaluate(() => document.body.innerHTML);
    console.log("--- BODY HTML START ---");
    console.log(bodyHtml);
    console.log("--- BODY HTML END ---");


    // The original check
    await page.waitForSelector('.mermaid svg', { timeout: 10000 });
    console.log('Mermaid diagram SVG element found. Verification successful.');

    const slides = await page.$$('.marp-slide');
    if (slides.length > 0) {
      await slides[0].screenshot({ path: 'slide_1.png' });
      console.log('Screenshot of Slide 1 saved as slide_1.png');
    }

  } catch (error) {
    console.error('Verification failed during SVG check:', error.message);
    // Take a screenshot on failure to see what the page looks like
    await page.screenshot({ path: 'failure_screenshot.png', fullPage: true });
    console.log('Failure screenshot saved to failure_screenshot.png');

  } finally {
    await browser.close();
  }
})();
