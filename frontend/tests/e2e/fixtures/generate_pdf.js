const { chromium } = require('@playwright/test');
const fs = require('fs');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const content = `
    <html>
      <body>
        <h1>RAG Evaluation Protocol</h1>
        <p>Research topic: retrieval augmented generation evaluation</p>
        <p>Required citation behavior: answers must cite source chunks</p>
        <p>Success metric: grounded, concise, and useful response</p>
      </body>
    </html>
  `;
  await page.setContent(content);
  await page.pdf({ path: 'facts.pdf', format: 'A4' });
  await browser.close();
})();
