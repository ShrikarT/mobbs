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

  console.log('1. Loading workbench...');
  await page.goto('http://127.0.0.1:58003/', { waitUntil: 'networkidle' });

  // Verify Flash button active
  const isFlashActive = await page.locator('button.btn-toggle:has-text("Flash (50 personas)")').getAttribute('class');
  console.log('Flash toggle active?', isFlashActive.includes('active'));

  console.log('2. Uploading Video A with Flash 50 profile...');
  await page.locator('#file-upload').setInputFiles(videoAPath);

  console.log('3. Waiting for live simulation grid panel...');
  await page.waitForSelector('.live-graph-panel', { timeout: 35000 });
  console.log('Live graph panel visible!');

  // Wait for several events to populate persona nodes
  console.log('Waiting for active/stopped persona nodes...');
  await page.waitForFunction(() => {
    const nodes = document.querySelectorAll('.persona-node.watching, .persona-node.stopped');
    return nodes.length >= 10;
  }, { timeout: 40000 });

  const activeCount = await page.locator('.persona-node.watching').count();
  const stoppedCount = await page.locator('.persona-node.stopped').count();
  console.log(`Live nodes observed: ${activeCount} watching, ${stoppedCount} stopped`);

  // Capture Live 50-persona grid screenshot
  await page.screenshot({ path: 'C:/Users/Shrikar/.codex/viralist-v03-ui/preview-live-grid.png' });
  console.log('Saved live grid screenshot to preview-live-grid.png');

  // Test Pause / Resume view button
  const pauseBtn = page.locator('button:has-text("Pause view")');
  console.log('Clicking Pause view...');
  await pauseBtn.click();
  await page.waitForSelector('.graph-paused-banner');
  console.log('Paused banner visible!');
  await page.waitForTimeout(1000);
  console.log('Clicking Resume view...');
  await page.locator('button:has-text("Resume view")').click();

  console.log('4. Waiting for report workbench (up to 150s)...');
  await page.waitForSelector('.workbench-grid', { timeout: 150000 });
  console.log('Report workbench is visible!');

  const verdict = await page.locator('.verdict-title').innerText();
  console.log('Verdict title:', verdict);

  const durationText = await page.locator('.timeline-header').innerText();
  console.log('Timeline duration:', durationText);

  const sceneCount = await page.locator('.timeline-segment').count();
  console.log('Scene segments count:', sceneCount);

  const retentionCount = await page.locator('.retention-table tbody tr').count();
  console.log('Retention table rows:', retentionCount);

  const notesCount = await page.locator('.note-card').count();
  console.log('Director notes count:', notesCount);

  const suppressedText = await page.locator('.suppressed-note-alert').innerText();
  console.log('Suppressed notes text:', suppressedText);

  // Capture Report Workbench screenshot
  await page.screenshot({ path: 'C:/Users/Shrikar/.codex/viralist-v03-ui/report-workbench.png' });
  console.log('Saved report workbench screenshot to report-workbench.png');

  // Open Trust Manifest & capture
  await page.locator('.trust-summary').click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: 'C:/Users/Shrikar/.codex/viralist-v03-ui/report-trust.png' });
  console.log('Saved trust manifest screenshot to report-trust.png');

  // Clean up: delete video & report
  console.log('5. Deleting video & report...');
  await page.locator('button:has-text("Delete video & report")').click();
  await page.waitForSelector('.modal-dialog');
  await page.locator('.modal-dialog button:has-text("Confirm deletion")').click();
  await page.waitForSelector('text=App-owned copies removed', { timeout: 30000 });
  console.log('Deletion complete!');

  await page.screenshot({ path: 'C:/Users/Shrikar/.codex/viralist-v03-ui/report-deleted.png' });
  console.log('Saved deletion screenshot to report-deleted.png');

  await browser.close();
  console.log('All checkpoints verified and captured successfully!');
}

main().catch(err => {
  console.error('Error:', err);
  process.exit(1);
});
