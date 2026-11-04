import { defineConfig, devices } from '@playwright/test';

const chromiumPath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || 'C:/Users/Shrikar/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 120000,
  expect: { timeout: 20000 },
  fullyParallel: false,
  retries: 0,
  workers: 1,
  use: {
    baseURL: process.env.MOBBS_E2E_BASE_URL || 'http://127.0.0.1:58000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    launchOptions: {
      executablePath: chromiumPath,
    },
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        launchOptions: { executablePath: chromiumPath },
      },
    },
    {
      name: 'mobile-320',
      use: {
        viewport: { width: 320, height: 640 },
        isMobile: true,
        launchOptions: { executablePath: chromiumPath },
      },
      grep: /Mobile viewport/,
    },
  ],
});
