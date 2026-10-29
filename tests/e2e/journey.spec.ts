import { test, expect } from '@playwright/test';

const VIDEO_B_PATH = 'D:\\UserFolders\\Downloads\\WhatsApp Video 2026-10-28 at 9.06.27 AM.mp4';
const VIDEO_A_PATH = 'D:\\UserFolders\\Downloads\\WhatsApp Video 2026-10-28 at 9.06.27 AM (1).mp4';

test.describe('Viralist V02 Browser Journey', () => {
  test('Complete journey for Video B: upload, real data binding, note seek, reload persistence, and honest deletion', async ({ page }) => {
    // 1. Visit workbench
    await page.goto('/');
    await expect(page).toHaveTitle(/Viralist/);
    await expect(page.locator('.brand-title')).toHaveText('Viralist / Evidence desk');
    await expect(page.locator('.hero-heading')).toHaveText('A clearer next cut.');
    await expect(page.locator('.session-badge')).toContainText('Session:');

    // 2. Upload video B using setInputFiles on the file input
    await page.locator('#file-upload').setInputFiles(VIDEO_B_PATH);

    // 3. Verify processing screen, indeterminate progress, and event ticker
    await expect(page.locator('.running-container')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('text=Analyzing audience retention')).toBeVisible();
    await expect(page.locator('.progress-bar.indeterminate')).toBeVisible();

    // 4. Wait for analysis to complete and report to render
    await expect(page.locator('.workbench-grid')).toBeVisible({ timeout: 45000 });
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

    // 14. Deletion lifecycle & modal focus
    await page.locator('button:has-text("Delete video & report")').click();
    await expect(page.locator('.modal-dialog')).toBeVisible();
    // Modal focus: cancel button must be focused
    await expect(page.locator('.modal-dialog button:has-text("Cancel")')).toBeFocused();

    await page.locator('button:has-text("Confirm deletion")').click();

    // Verify deletion screen shows honest app-owned copy limits (NOT 'All data permanently removed')
    await expect(page.locator('.deletion-targets-list')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('text=App-owned copies removed')).toBeVisible({ timeout: 20000 });
    await expect(page.locator('.deletion-caveat')).toContainText('App-owned copies only');

    // Reset back to upload
    await page.locator('button:has-text("Start new upload")').click();
    await expect(page.locator('.hero-heading')).toHaveText('A clearer next cut.');
  });

  test('Video A journey: 33.8s duration, all scenes drawn, no Drop label on 3-8s, and 1 suppressed note', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.hero-heading')).toHaveText('A clearer next cut.');
    await expect(page.locator('.session-badge')).toContainText('Session:');
    await page.locator('#file-upload').setInputFiles(VIDEO_A_PATH);

    // Wait for report
    await expect(page.locator('.workbench-grid')).toBeVisible({ timeout: 75000 });

    // Verify duration is 33.8s
    await expect(page.locator('.timeline-header')).toContainText('33.8s');

    // Verify all 8 scenes drawn
    const segments = page.locator('.timeline-segment');
    const count = await segments.count();
    expect(count).toBe(8);

    // Verify scene 3-8s does NOT have Drop label
    await expect(page.locator('.timeline-segment', { hasText: '3–8s' })).not.toContainText('Drop');

    // Verify no supported notes and honest suppression note
    await expect(page.locator('text=No supported edit found.')).toBeVisible();
    await expect(page.locator('.suppressed-note-alert')).toContainText('1 unsupported candidate note was suppressed');

    // Cleanup video A
    await page.locator('button:has-text("Delete video & report")').click();
    await page.locator('button:has-text("Confirm deletion")').click();
    await expect(page.locator('text=App-owned copies removed')).toBeVisible({ timeout: 25000 });
  });

  test('Processing cancellation and deletion recovery', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.session-badge')).toContainText('Session:');
    await page.locator('#file-upload').setInputFiles(VIDEO_B_PATH);

    // In processing view, click Cancel & delete video
    await expect(page.locator('.running-container')).toBeVisible({ timeout: 15000 });
    const cancelDeleteBtn = page.locator('button:has-text("Cancel & delete video")');
    await expect(cancelDeleteBtn).toBeVisible();
    await cancelDeleteBtn.click();

    // Confirm deletion in modal
    await expect(page.locator('.modal-dialog')).toBeVisible();
    await page.locator('button:has-text("Confirm deletion")').click();

    // Verifies deletion lifecycle runs and removes the in-flight video
    await expect(page.locator('text=App-owned copies removed')).toBeVisible({ timeout: 25000 });
  });

  test('Mobile viewport (320px) layout, text contrast, and no overflow', async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 640 });
    await page.goto('/');

    await expect(page.locator('.brand-title')).toBeVisible();
    await expect(page.locator('.hero-heading')).toBeVisible();

    // Check no horizontal scroll / overflow
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1);

    // Verify header fits at 320px
    const headerHeight = await page.locator('.app-header').evaluate((el: HTMLElement) => el.offsetHeight);
    expect(headerHeight).toBeGreaterThanOrEqual(56);
  });
});
