import { chromium } from '@playwright/test';

const chromiumPath = 'C:/Users/Shrikar/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe';

async function main() {
  const browser = await chromium.launch({
    executablePath: chromiumPath,
    headless: true,
  });
  const page = await browser.newPage();
  page.on('console', msg => console.log('BROWSER CONSOLE:', msg.type(), msg.text()));
  page.on('pageerror', err => console.log('PAGE ERROR:', err.message, err.stack));

  console.log('Navigating to http://127.0.0.1:58003/ ...');
  const res = await page.goto('http://127.0.0.1:58003/', { waitUntil: 'networkidle' });
  console.log('Response status:', res?.status());
  console.log('Title:', await page.title());
  const bodyText = await page.evaluate(() => document.body.innerText);
  console.log('Body text length:', bodyText.length);
  console.log('Body text sample:', bodyText.slice(0, 200));

  await page.screenshot({ path: 'C:/Users/Shrikar/.codex/viralist-v03-ui/playwright-preview.png' });
  console.log('Saved screenshot to playwright-preview.png');
  await browser.close();
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
