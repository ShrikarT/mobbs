import { chromium } from '@playwright/test';
import fs from 'fs';

const chromiumPath = 'C:/Users/Shrikar/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe';

function getMediaA() {
  const meta = JSON.parse(fs.readFileSync('C:/Users/Shrikar/.codex/private-runs/viralist-spark13-20261028/stage2-bounded/media.json', 'utf8'));
  return meta.a.path;
}

async function main() {
  const videoAPath = getMediaA();
  console.log('Video A path:', videoAPath);

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

  console.log('1. Loading landing desk...');
  await page.goto('http://127.0.0.1:58003/', { waitUntil: 'networkidle' });

  // Verify Flash is selected by default
  const flashBtn = page.locator('button.btn-toggle:has-text("Flash (50 personas)")');
  console.log('Flash button class:', await flashBtn.getAttribute('class'));

  console.log('2. Uploading Video A...');
  await page.locator('#file-upload').setInputFiles(videoAPath);

  console.log('3. Waiting for processing screen...');
  await page.waitForSelector('.running-container', { timeout: 20000 });
  console.log('Processing screen visible!');

  // Wait a few seconds for simulation events to arrive and capture live grid
  await page.waitForTimeout(4000);
  const eventItemsCount = await page.locator('.persona-node.watching, .persona-node.stopped').count();
  console.log('Active/stopped persona nodes so far:', eventItemsCount);

  // Take live processing screenshot
  await page.screenshot({ path: 'C:/Users/Shrikar/.codex/viralist-v03-ui/preview-processing.png' });
  console.log('Saved processing screenshot to preview-processing.png');

  // Test Pause / Resume view button
  const pauseBtn = page.locator('button:has-text("Pause view")');
  if (await pauseBtn.isVisible()) {
    console.log('Clicking Pause view...');
    await pauseBtn.click();
    await page.waitForSelector('.graph-paused-banner');
    console.log('Paused banner visible!');
    await page.waitForTimeout(1000);
    console.log('Clicking Resume view...');
    await page.locator('button:has-text("Resume view")').click();
  }

  console.log('4. Waiting for report workbench...');
  await page.waitForSelector('.workbench-grid', { timeout: 90000 });
  console.log('Report workbench visible!');

  // Verify elements
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

  // Take report screenshot
  await page.screenshot({ path: 'C:/Users/Shrikar/.codex/viralist-v03-ui/preview-report.png' });
  console.log('Saved report screenshot to preview-report.png');

  // Open trust manifest
  await page.locator('.trust-summary').click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: 'C:/Users/Shrikar/.codex/viralist-v03-ui/preview-trust.png' });
  console.log('Saved trust manifest screenshot to preview-trust.png');

  // Clean up: delete video & report
  console.log('5. Deleting video & report...');
  await page.locator('button:has-text("Delete video & report")').click();
  await page.waitForSelector('.modal-dialog');
  await page.locator('.modal-dialog button:has-text("Confirm deletion")').click();
  await page.waitForSelector('text=App-owned copies removed', { timeout: 30000 });
  console.log('Deletion confirmed complete!');

  await page.screenshot({ path: 'C:/Users/Shrikar/.codex/viralist-v03-ui/preview-deleted.png' });
  console.log('Saved deletion screenshot to preview-deleted.png');

  await browser.close();
  console.log('Full journey check completed successfully!');
}

main().catch(err => {
  console.error('Error in main:', err);
  process.exit(1);
});
