import { defineConfig, devices } from '@playwright/test';

const chromiumPath = 'C:/Users/Shrikar/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 480000,
  expect: { timeout: 25000 },
  fullyParallel: false,
  retries: 0,
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:58003',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    launchOptions: {
      executablePath: chromiumPath,
    },
  },
  projects: [
    {
      name: 'chromium',
      grepInvert: /Mobile viewport/,
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
