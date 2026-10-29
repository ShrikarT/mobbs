import { test, expect } from '@playwright/test';

const VIDEO_B_PATH = 'D:\\UserFolders\\Downloads\\WhatsApp Video 2026-10-28 at 9.06.27 AM.mp4';

test.describe('Viralist V02 Browser Journey', () => {
  test('Complete journey: upload, simulated analysis, note seek, reload persistence, and deletion', async ({ page }) => {
    // 1. Visit workbench
    await page.goto('/');
    await expect(page).toHaveTitle(/Viralist/);
    await expect(page.locator('.brand-title')).toHaveText('Viralist / Evidence desk');
    await expect(page.locator('.hero-heading')).toHaveText('A clearer next cut.');

    // 2. Upload video B using setInputFiles on the file input
    await page.locator('#file-upload').setInputFiles(VIDEO_B_PATH);

    // 3. Verify processing screen and progress
    await expect(page.locator('.running-container')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('text=Analyzing audience retention')).toBeVisible();

    // 4. Wait for analysis to complete and report to render
    await expect(page.locator('.workbench-grid')).toBeVisible({ timeout: 45000 });
    await expect(page.locator('.verdict-title')).toHaveText('Executive finding');

    // 5. Verify cast metrics
    await expect(page.locator('.metric-pill', { hasText: 'Cast:' })).toContainText('3 viewers');
    await expect(page.locator('.metric-pill', { hasText: 'Stopped viewers:' })).toContainText('3');

    // 6. Verify supported Director's Note
    const noteCard = page.locator('.note-card').first();
    await expect(noteCard).toBeVisible();
    await expect(noteCard.locator('.note-timestamp')).toContainText('3.0s – 8.0s');
    await expect(noteCard.locator('.quotes-section')).toBeVisible();
    await expect(noteCard.locator('.quotes-heading')).toHaveText('Simulated persona reason');

    // 7. Verify video seeking on note click
    await noteCard.click();
    const video = page.locator('video');
    await expect(video).toBeVisible();
    const currentTime = await video.evaluate((el: HTMLVideoElement) => el.currentTime);
    expect(currentTime).toBeGreaterThanOrEqual(3.0);

    // 8. Verify suppressed note alert
    await expect(page.locator('.suppressed-note-alert')).toContainText('1 unsupported candidate note was suppressed');

    // 9. Verify reload persistence (A08)
    await page.reload();
    await expect(page.locator('.workbench-grid')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('.verdict-title')).toHaveText('Executive finding');
    await expect(page.locator('.note-card').first()).toBeVisible();

    // 10. Open trust manifest
    await page.locator('.trust-summary').click();
    await expect(page.locator('text=Recorded inference · exact original media')).toBeVisible();
    await expect(page.locator('text=muse-spark-1.3')).toBeVisible();

    // 11. Deletion lifecycle
    await page.locator('button:has-text("Delete video & report")').click();
    await expect(page.locator('.modal-dialog')).toBeVisible();
    await page.locator('button:has-text("Confirm deletion")').click();

    // Verify deletion screen and target breakdown
    await expect(page.locator('.deletion-targets-list')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('text=All data permanently removed')).toBeVisible({ timeout: 20000 });

    // Reset back to upload
    await page.locator('button:has-text("Start new upload")').click();
    await expect(page.locator('.hero-heading')).toHaveText('A clearer next cut.');
  });

  test('Mobile viewport (320px) accessibility and layout', async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 640 });
    await page.goto('/');

    await expect(page.locator('.brand-title')).toBeVisible();
    await expect(page.locator('.hero-heading')).toBeVisible();

    // Check no horizontal scroll / overflow
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1); // 1px rounding tolerance
  });

  test('Keyboard navigation and accessibility', async ({ page }) => {
    await page.goto('/');
    // Tab into dropzone / input
    await page.keyboard.press('Tab');
    const focusedTag = await page.evaluate(() => document.activeElement?.tagName);
    expect(['A', 'BUTTON', 'INPUT', 'LABEL', 'DIV']).toContain(focusedTag);
  });
});
