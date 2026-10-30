import { chromium } from '@playwright/test';

const chromiumPath = 'C:/Users/Shrikar/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe';

async function main() {
  const browser = await chromium.launch({
    executablePath: chromiumPath,
    headless: true,
  });
  const page = await browser.newPage({
    viewport: { width: 1280, height: 900 }
  });

  page.on('console', msg => {
    if (msg.type() === 'error') console.log('BROWSER ERROR:', msg.text());
  });

  console.log('Navigating to workbench...');
  await page.goto('http://127.0.0.1:58003/', { waitUntil: 'networkidle' });

  await page.waitForSelector('.workbench-grid', { timeout: 15000 });
  console.log('Report workbench is visible!');

  const verdict = await page.locator('.verdict-title').innerText();
  console.log('Verdict:', verdict);

  const durationText = await page.locator('.timeline-header').innerText();
  console.log('Timeline duration:', durationText);

  const sceneSegments = await page.locator('.timeline-segment').count();
  console.log('Scene count in timeline:', sceneSegments);

  const retentionRows = await page.locator('.retention-table tbody tr').count();
  console.log('Retention table rows:', retentionRows);

  const suppressedText = await page.locator('.suppressed-note-alert').innerText();
  console.log('Suppressed notes notice:', suppressedText);

  await page.screenshot({ path: 'C:/Users/Shrikar/.codex/viralist-v03-ui/report-workbench.png' });
  console.log('Saved report workbench screenshot to report-workbench.png');

  // Open trust manifest details
  await page.locator('.trust-summary').click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: 'C:/Users/Shrikar/.codex/viralist-v03-ui/report-trust.png' });
  console.log('Saved trust manifest screenshot to report-trust.png');

  await browser.close();
  console.log('Done.');
}

main().catch(err => {
  console.error('Error:', err);
  process.exit(1);
});
