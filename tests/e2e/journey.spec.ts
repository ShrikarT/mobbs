import { test, expect } from '@playwright/test';
import fs from 'fs';

function getMediaPaths() {
  try {
    const aJson = JSON.parse(
      fs.readFileSync('C:/Users/Shrikar/.codex/private-runs/viralist-spark13-20261028/stage2-bounded/media.json', 'utf8')
    );
    const bJson = JSON.parse(
      fs.readFileSync('C:/Users/Shrikar/.codex/private-runs/viralist-spark13-20261028/stage1-bounded/media.json', 'utf8')
    );
    return { aPath: aJson.a.path, bPath: bJson.b.path };
  } catch {
    return {
      aPath: 'D:\\UserFolders\\Downloads\\WhatsApp Video 2026-10-28 at 9.06.27 AM (1).mp4',
      bPath: 'D:\\UserFolders\\Downloads\\WhatsApp Video 2026-10-28 at 9.06.27 AM.mp4',
    };
  }
}

const { aPath: VIDEO_A_PATH, bPath: VIDEO_B_PATH } = getMediaPaths();

test.describe('Mobbs V03 Browser Journey', () => {
  test('Complete journey for Video B (Test 3): upload, real data binding, note seek, reload persistence, modal containment, and honest deletion', async ({
    page,
  }) => {
    test.setTimeout(180000);
    // 1. Visit workbench
    await page.goto('/#/app');
    await expect(page).toHaveTitle(/mobbs/i);
    await expect(page.locator('.brand-title')).toHaveText('mobbs.fun');
    await expect(page.locator('.hero-heading')).toHaveText('what are we watching?');
    await expect(page.locator('.session-badge')).toContainText('Session:');

    // Select Test (3 personas) profile for Video B
    const testToggle = page.locator('button.btn-toggle:has-text("Test (3 personas)")');
    await testToggle.click();
    await expect(testToggle).toHaveClass(/active/);

    // 2. Upload video B using setInputFiles on the file input
    await page.locator('#file-upload').setInputFiles(VIDEO_B_PATH);

    // 3. Verify processing screen, indeterminate progress, and event ticker
    await expect(page.locator('.running-container')).toBeVisible({ timeout: 30000 });
    await expect(page.getByRole('heading', {name:'a little crowd. big feelings.'})).toBeVisible({ timeout: 100000 });
    await expect(page.locator('.progress-bar.indeterminate')).toBeVisible();

    // 4. Wait for analysis to complete and report to render
    await expect(page.locator('.workbench-grid')).toBeVisible({ timeout: 100000 });
    await expect(page.locator('.verdict-title')).toHaveText('Executive finding');

    // 5. Verify duration heading reflects exact media duration (17.1s, not 3s)
    await expect(page.locator('.timeline-header')).toContainText('17.1s');

    // 6. Verify timeline segments and stop trigger for B (3-8s Drop)
    const triggerSegment = page.locator('.timeline-segment.has-trigger').filter({ hasText: '3–8s' });
    await expect(triggerSegment).toBeVisible();
    await expect(triggerSegment).toContainText('3–8s (Drop)');

    // 7. Verify cast metrics
    await expect(page.locator('.metric-pill', { hasText: 'Cast:' })).toContainText('3 viewers');
    await expect(page.locator('.metric-pill', { hasText: 'Stopped viewers:' })).toContainText('3');
    await expect(page.locator('.metric-pill', { hasText: 'Completion rate:' })).toBeVisible();
    await expect(page.locator('.metric-method')).toContainText('nearest-rank p10–p90');

    // 8. Verify supported Director's Note
    const noteCard = page.locator('.note-card').first();
    await expect(noteCard).toBeVisible();
    await expect(noteCard.locator('.note-timestamp')).toContainText('3.0s – 8.0s');
    await expect(noteCard.locator('.quotes-section')).toBeVisible();
    await expect(noteCard.locator('.quotes-heading')).toHaveText('Simulated persona reason');

    // 9. Verify video seeking on note click
    await noteCard.click();
    const video = page.locator('video');
    await expect(video).toBeVisible();
    const currentTime = await video.evaluate((el: HTMLVideoElement) => el.currentTime);
    expect(currentTime).toBeGreaterThanOrEqual(3.0);

    // 9b. Verify keyboard operability on evidence quote button (Enter/Space opens inspector without clearing note)
    const quoteBtn = noteCard.locator('button.quote-button').first();
    await expect(quoteBtn).toBeVisible();
    await quoteBtn.focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('.evidence-inspector-card')).toBeVisible();
    await expect(noteCard).toHaveClass(/selected/);

    // 10. Verify timeline keyboard seek
    await triggerSegment.focus();
    await page.keyboard.press('Enter');
    const seekTime = await video.evaluate((el: HTMLVideoElement) => el.currentTime);
    expect(seekTime).toBeGreaterThanOrEqual(3.0);

    // 11. Verify honest suppressed note count for B (0 unsupported notes, not 1)
    await expect(page.locator('.suppressed-note-alert')).toContainText('0 unsupported candidate notes were suppressed');

    // 12. Verify reload persistence (A08)
    await page.reload();
    await expect(page.locator('.workbench-grid')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('.verdict-title')).toHaveText('Executive finding');
    await expect(page.locator('.timeline-header')).toContainText('17.1s');
    await expect(page.locator('.note-card').first()).toBeVisible();

    // 13. Open trust manifest & verify methodology / limitations
    await page.locator('.trust-summary').click();
    await expect(page.locator('text=Recorded inference · exact original media')).toBeVisible();
    await expect(page.locator('text=muse-spark-1.3')).toBeVisible();
    await expect(page.locator('dt:has-text("Training cutoff:") + dd')).toHaveText('not provided');
    await expect(page.locator('text=Methodology assumptions:')).toBeVisible();
    await expect(page.locator('text=Simulation limitations:')).toBeVisible();
    await expect(page.locator('.thin-cast-notice')).not.toContainText('Flash 50');
    await expect(page.locator('.thin-cast-notice')).toContainText('Test 3 cast');

    // 14. Modal focus lifecycle and boundary containment
    const reportDeleteBtn = page.locator('button:has-text("Delete video & report")');
    await reportDeleteBtn.click();
    await expect(page.locator('.modal-dialog')).toBeVisible();

    // Modal initial focus on Cancel
    const cancelBtn = page.locator('.modal-dialog button:has-text("Cancel")');
    const confirmBtn = page.locator('.modal-dialog button:has-text("Confirm deletion")');
    await expect(cancelBtn).toBeFocused();

    // Forward Tab traversal: Cancel -> Confirm -> Cancel
    await page.keyboard.press('Tab');
    await expect(confirmBtn).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(cancelBtn).toBeFocused();

    // Reverse Tab traversal: Cancel -> Confirm -> Cancel
    await page.keyboard.press('Shift+Tab');
    await expect(confirmBtn).toBeFocused();
    await page.keyboard.press('Shift+Tab');
    await expect(cancelBtn).toBeFocused();

    // Escape key closes dialog and restores focus to trigger button
    await page.keyboard.press('Escape');
    await expect(page.locator('.modal-dialog')).not.toBeVisible();
    await expect(reportDeleteBtn).toBeFocused();

    // 15. Re-open modal and confirm deletion lifecycle
    await reportDeleteBtn.click();
    await expect(page.locator('.modal-dialog')).toBeVisible();
    await confirmBtn.click();

    // Verify deletion screen shows honest pending state or completed state
    await expect(page.locator('.deletion-targets-list')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('.deletion-caveat')).toContainText('App-owned copies only');

    // Wait for completed removal
    await expect(page.locator('text=App-owned copies removed')).toBeVisible({ timeout: 60000 });
    await expect(page.locator('text=Controlled artifacts removed from PostgreSQL and private storage.')).toBeVisible();
    await expect(page.locator('.deletion-caveat')).toContainText(
      'App-owned copies only. Historical source evidence and upstream backups are not erased by this operation.'
    );

    // Reset back to upload
    await page.locator('button:has-text("Start new upload")').click();
    await expect(page.locator('.hero-heading')).toHaveText('what are we watching?');
  });

  test('Video A journey (Flash 50): 50 requested, live graph, 33.8s duration, 8 scenes, 8 retention rows, 0 supported notes, 1 suppressed note', async ({
    page,
  }) => {
    test.setTimeout(450000);
    await page.goto('/#/app');
    await expect(page.locator('.hero-heading')).toHaveText('what are we watching?');
    await expect(page.locator('.session-badge')).toContainText('Session:');

    // Verify Flash (50 personas) is active by default
    const flashToggle = page.locator('button.btn-toggle:has-text("Flash (50 personas)")');
    await expect(flashToggle).toHaveClass(/active/);

    // Upload Video A
    await page.locator('#file-upload').setInputFiles(VIDEO_A_PATH);

    // Verify processing screen and live persona graph panel
    await expect(page.locator('.running-container')).toBeVisible({ timeout: 30000 });
    await expect(page.locator('.live-graph-panel')).toBeVisible({ timeout: 120000 });

    // Test Pause / Resume view button
    const pauseBtn = page.locator('button:has-text("Pause view")');
    await expect(pauseBtn).toBeVisible();
    await pauseBtn.click();
    await expect(page.locator('.graph-paused-banner')).toBeVisible();
    await page.locator('button:has-text("Resume view")').click();
    await expect(page.locator('.graph-paused-banner')).not.toBeVisible();

    // Wait for report (sequential 50 personas takes ~260-290s)
    await expect(page.locator('.workbench-grid')).toBeVisible({ timeout: 350000 });

    // Verify duration is 33.8s
    await expect(page.locator('.timeline-header')).toContainText('33.8s');

    // Verify all 8 scenes drawn
    const segments = page.locator('.timeline-segment');
    const count = await segments.count();
    expect(count).toBe(8);

    // Verify scene 3-8s does NOT have Drop label
    await expect(page.locator('.timeline-segment', { hasText: '3–8s' })).not.toContainText('Drop');

    // Verify Retention table has 8 rows
    const retentionRows = page.locator('.retention-table tbody tr');
    expect(await retentionRows.count()).toBe(8);

    // Verify unavailable drop rate for zero-entrant final scene row (scene 7)
    const scene7Row = retentionRows.filter({ hasText: 'Scene 7' });
    await expect(scene7Row).toContainText('Unavailable');
    await expect(scene7Row).toContainText('no_scene_entrants');

    // Verify Hook and Pacing scores visible
    await expect(page.locator('.score-item', { hasText: 'Hook Score' })).toContainText('78.0%');
    await expect(page.locator('.score-item', { hasText: 'Pacing Score' })).toContainText('58.0%');

    // Verify unobserved signals are explicitly marked Unavailable
    await expect(page.locator('.score-item', { hasText: 'Clarity Index' })).toContainText('Unavailable');
    await expect(page.locator('.score-item', { hasText: 'CTA Index' })).toContainText('Unavailable');
    await expect(page.locator('.score-item', { hasText: 'Trend Fit' })).toContainText('Unavailable');

    // Verify Engagement: follow is marked Unavailable
    await expect(page.locator('.engagement-item', { hasText: 'FOLLOW' })).toContainText('Unavailable');

    // Verify no supported notes and honest suppression note with rejection breakdown
    await expect(page.locator('text=No supported edit found.')).toBeVisible();
    await expect(page.locator('.no-notes-banner')).not.toContainText('statistical support threshold');
    await expect(page.locator('.no-notes-banner')).not.toContainText('11 personas stopped');
    await expect(page.locator('.suppressed-note-alert')).toContainText('1 unsupported candidate note was suppressed');
    await expect(page.locator('.rejection-breakdown')).toContainText('unsupported_trigger: 1');

    // Verify 5-archetype thin library disclosure in trust section
    await page.locator('.trust-summary').click();
    await expect(page.locator('.thin-cast-notice')).toContainText('5 documented tech/product archetypes across 50 instances');

    // Cleanup video A
    const delBtn = page.locator('button:has-text("Delete video & report")');
    await delBtn.click();
    await page.locator('.modal-dialog button:has-text("Confirm deletion")').click();
    await expect(page.locator('text=App-owned copies removed')).toBeVisible({ timeout: 60000 });
  });

  test('Video B with Flash requested: truthful error handling and recovery', async ({ page }) => {
    test.setTimeout(180000);
    await page.goto('/#/app');
    await expect(page.locator('.session-badge')).toContainText('Session:');

    // Select Flash profile
    const flashToggle = page.locator('button.btn-toggle:has-text("Flash (50 personas)")');
    await flashToggle.click();

    // Upload Video B (which does NOT support recorded Flash)
    await page.locator('#file-upload').setInputFiles(VIDEO_B_PATH);

    // Expect operation failure screen with explicit error message
    await expect(page.locator('.running-container')).toBeVisible({ timeout: 60000 });
    await expect(page.getByRole('heading', {name:'Analysis failed',exact:true})).toBeVisible({ timeout: 120000 });
    await expect(page.locator('text=recorded_evidence_unavailable_for_this_upload')).toBeVisible();

    // Recovery button works
    const tryAgainBtn = page.getByRole('button', {name:'Return to upload',exact:true});
    await expect(tryAgainBtn).toBeVisible();
    await tryAgainBtn.click();

    // Returns to upload landing desk
    await expect(page.locator('.hero-heading')).toHaveText('what are we watching?');
  });

  test('Processing cancellation, modal containment, and pending/completed truth', async ({ page }) => {
    test.setTimeout(180000);
    await page.goto('/#/app');
    await expect(page.locator('.session-badge')).toContainText('Session:');

    // Select Test 3 profile for quick start
    await page.locator('button.btn-toggle:has-text("Test (3 personas)")').click();
    await page.locator('#file-upload').setInputFiles(VIDEO_B_PATH);

    // In processing view, click Cancel & delete video
    await expect(page.locator('.running-container')).toBeVisible({ timeout: 30000 });
    const cancelDeleteBtn = page.locator('button:has-text("Cancel & delete video")');
    await expect(cancelDeleteBtn).toBeVisible({ timeout: 100000 });

    // Test modal containment in processing view
    await cancelDeleteBtn.click();
    await expect(page.locator('.modal-dialog')).toBeVisible();
    const cancelBtn = page.locator('.modal-dialog button:has-text("Cancel")');
    const confirmBtn = page.locator('.modal-dialog button:has-text("Confirm deletion")');
    await expect(cancelBtn).toBeFocused();

    // Tab traversal
    await page.keyboard.press('Tab');
    await expect(confirmBtn).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(cancelBtn).toBeFocused();

    // Escape closes and restores focus to Cancel & delete video button
    await page.keyboard.press('Escape');
    await expect(page.locator('.modal-dialog')).not.toBeVisible();
    await expect(cancelDeleteBtn).toBeFocused();

    // Re-open and confirm
    await cancelDeleteBtn.click();
    await confirmBtn.click();

    // Verifies deletion lifecycle runs and removes the in-flight video
    await expect(page.locator('text=App-owned copies removed')).toBeVisible({ timeout: 60000 });
    await expect(page.locator('text=Controlled artifacts removed from PostgreSQL and private storage.')).toBeVisible();
  });

  test('Mobile viewport (320px) header, profile selector, and horizontal overflow', async ({ page }) => {
    test.setTimeout(60000);
    await page.setViewportSize({ width: 320, height: 640 });
    await page.goto('/#/app');

    await expect(page.locator('.brand-title')).toBeVisible();
    await expect(page.locator('.hero-heading')).toBeVisible();

    // Check no horizontal scroll / overflow
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1);

    // Verify header fits at 320px
    const headerHeight = await page.locator('.app-header').evaluate((el: HTMLElement) => el.offsetHeight);
    expect(headerHeight).toBeGreaterThanOrEqual(56);

    // Verify profile selector buttons fit
    const toggle = page.locator('button.btn-toggle').first();
    await expect(toggle).toBeVisible();
    const toggleWidth = await toggle.evaluate((el: HTMLElement) => el.offsetWidth);
    expect(toggleWidth).toBeLessThanOrEqual(320);
  });
});
